"""Verify language-list resource selection and complete entry fixtures offline."""
import argparse
import hashlib
import json
from pathlib import Path
from analyze_banked_abi import SHA, inventory
from emulate_mcs51 import Machine
from map_osd_atlas import base_font_candidate
from map_osd_language_layout import Window


class Selected(Exception):pass


class Name(Machine):
    def readx(self,address):
        if (self.bank,self.origin,address) == (1,0xDCA7,0xD852):raise Selected
        return super().readx(address)


class FullEntry(Window):
    def __init__(self,*args):
        super().__init__(*args);self.names = []
    def jump(self,target,call=False):
        if (self.bank,self.origin,target) == (10,0xD1BB,0x1A4E):
            self.names.append({'index':self.x[0xD82F],
                               'row':self.r(7),'column':self.r(5),'style':self.r(3),
                               'context':tuple(self.x[0xD853:0xD856])})
        super().jump(target,call)


def build(data,full=True):
    assert len(data) == 0xE0000 and hashlib.sha256(data).hexdigest() == SHA
    thunks = inventory(data)
    assert thunks[0x1A4E] == (1,0xDC4F)
    q = Machine(data,thunks);q.sr(7,0x0E);q.sr(5,0)
    q.run(1,0xE43B,budget=100)
    assert (q.r(3),q.r(2),q.r(1)) == (255,0x6D,0x77)
    chunk = data[65536:131072];base = 0x6D77;limit = 0x6E1B
    assert chunk[base:limit].count(255) == 21
    records = [];start = base
    for index in range(21):
        end = chunk.index(255,start,limit)
        for stored in (0,index,20):
            m = Name(data,thunks);m.x[0xDA03] = stored
            m.x[0xD853:0xD856] = bytes((14,0,index))
            m.sr(7,5+2*(index%8));m.sr(5,26+13*(index//8));m.sr(3,3)
            try:m.run(1,0xDC4F,budget=10000)
            except Selected:pass
            else:raise AssertionError('Expected name-segment boundary')
            assert bytes(m.x[0xD874:0xD877]) == bytes((255,start>>8,start&255))
            assert m.x[0xD855] == index and m.x[0xDA03] == stored
            assert bytes(m.x[0xD850:0xD853]) == bytes((5+2*(index%8),26+13*(index//8),3))
            assert m.ram[0x26] == 0
        records.append({'index':index,'segment_start':f'1:{start:04X}',
                        'segment_end':f'1:{end:04X}','length':end-start,
                        'row':5+2*(index%8),'column':26+13*(index//8),
                        'base_font_candidate':base_font_candidate(chunk[start:end])})
        start = end+1
    assert start == limit
    entries = []
    if full:
        for language in range(21):
            m = FullEntry(data,thunks);m.x[0xDA6B] = 0x32;m.x[0xDA03] = language
            m.x[0xDAD3:0xDAD7] = (60000000).to_bytes(4,'big')
            m.x[0xFFFF] = 13;m.ram[0x39] = 1
            m.x[0xDC09] = 40;m.x[0xDBFC] = 40
            m.run(9,0xF550,budget=2000000)
            assert m.x[0xDA6B] == 0x56 and m.x[0xDA03] == language
            assert bytes(m.x[0xDA48:0xDA4A]) == bytes((0,language))
            assert not m.calls and not m.stack
            assert len(m.names) == 21
            for index,n in enumerate(m.names):
                assert n == {'index':index,'row':5+2*(index%8),
                             'column':26+13*(index//8),'style':3,'context':(14,0,index)}
            assert not ({a for _,_,a in m.writes}&set(range(0xFF55,0xFF5F)))
            entries.append({'stored_language':language,'steps':m.steps,
                            'list_calls':len(m.names),'window_bursts':len(m.frames),
                            'port_writes':len(m.ports),'return_setting':'56',
                            'preview':language})
            print('Full entry fixture:',language,'steps:',m.steps,flush=True)
    return {'firmware_sha256':SHA,'name_selection_checks':63,
            'full_entry_checks':len(entries),'segments':records,'entry_fixtures':entries,
            'resource':'Family0E/index0 ->code1:6D77, exactly21 FF-delimited name segments before next family09 resource1:6E1B.',
            'selector':'1:DC4F/FC8F/E43B resolves family D853=0E/indexD854=0; actual DC8A..DCA2 loop skips D855 name segments. It uses explicit index, independently of stored DA03 in checked fixtures.',
            'list':'10:D153..D1C1 iterates D82F0..20; D1BB ->1A4E/1:DC4F receives rows5+2*(index%8), columns26+13*(index//8), style3 and D853:D854:D855=0E:00:index.',
            'full_entry':'9:F550 returns with DA6B56 and DA48:DA49=00:stored-language after21 list calls in each complete fixture. No drawing callee is skipped.',
            'limits':['Every fixture executes offline in bounded interpreter, not on a monitor.',
                      'Full entry uses Window synthetic FFF3 busy-bit completion, RAM39=1, FFFF=13, DAD3=60000000 and DC09/DBFC=40. These are fixtures, not proven live startup state.',
                      'Burst-engine copies, display visibility, interrupts and physical timing are not emulated.',
                      'Base-font candidates reuse the atlas partial alphabet; extension tokens and duplicated letters remain unresolved. Do not promote candidates to complete language-ID names.',
                      'Only ordinary row32 command0 entry is integrated, not all exit/apply/re-entry state variants.']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('firmware',type=Path);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--segments-only',action='store_true',help='Exclude expensive full-entry fixtures')
    args = p.parse_args();result = build(args.firmware.read_bytes(),not args.segments_only)
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print('Name/full-entry checks:',result['name_selection_checks'],result['full_entry_checks'])


if __name__ == '__main__':main()

"""Verify multilingual segment traversal and text control classification offline."""
import argparse
import hashlib
import json
from pathlib import Path
from analyze_banked_abi import SHA, inventory
from emulate_mcs51 import Machine


class SegmentSelected(Exception):
    pass


class SegmentMachine(Machine):
    def readx(self, address):
        if (self.bank,self.origin,address)==(1,0xD7F4,0xD83E):
            raise SegmentSelected
        return super().readx(address)


def select(data, thunks, tag, start, count, payload=None):
    m=SegmentMachine(data,thunks)
    m.x[0xD861:0xD864]=bytes([tag])+start.to_bytes(2,'big')
    m.ram[0x26]=count
    if payload is not None:
        m.x[start:start+len(payload)]=payload
    try:
        m.run(1,0xD7D7,budget=30000)
    except SegmentSelected:
        pass
    else:
        raise AssertionError('Expected selection boundary')
    assert m.ram[0x26]==0
    assert {a for _,_,a in m.writes} <= {0xD862,0xD863}
    return int.from_bytes(m.x[0xD862:0xD864],'big'),m.steps


def build(data):
    assert len(data)==0xE0000 and hashlib.sha256(data).hexdigest()==SHA
    thunks=inventory(data)
    synthetic=0
    # Unequal lengths, empty segments, control bytes and address carry exercise
    # the firmware scanner independently from a high-level split model.
    segments=[b'',b'\x01',b'\xfa\x02\xfd\x03',bytes(range(70)),b'\xfe\x0c']
    payload=b'\xff'.join(segments)+b'\xff'
    for start in (0x9000,0x90FC,0x91FF):
        for count in range(len(segments)):
            actual,steps=select(data,thunks,1,start,count,payload)
            expected=start+sum(len(s)+1 for s in segments[:count])
            assert actual==expected,(start,count,actual,expected)
            synthetic+=1
    warning=[]
    chunk=data[65536:131072]
    start=0xA0EF
    expected=start
    # The next independently resolved resource begins at A317. Count delimiters
    # within that interval, without equating them with supported language IDs.
    assert chunk[start:0xA317].count(255)==21
    for count in range(21):
        actual,steps=select(data,thunks,0xFF,start,count)
        assert actual==expected
        end=chunk.index(255,actual)
        warning.append({'skip_count':count,'start':f'1:{actual:04X}',
                        'length':end-actual,'terminator':f'1:{end:04X}',
                        'steps':steps})
        expected=end+1
    assert expected==0xA317
    special=[]
    for token in range(256):
        m=Machine(data,thunks)
        m.sr(7,token)
        # Enter the actual first classification with A holding the fetched byte.
        m.a=token
        class Halt(Exception):pass
        def jump(target,call=False):
            if target in (0xD86D,0xCE0F):raise Halt
            Machine.jump(m,target,call)
        m.jump=jump
        try:m.run(1,0xD803,budget=50)
        except Halt:pass
        classified=(1,0xD825) in m.visited
        assert classified==(0xF8<=token<=0xFE),(token,classified)
        if classified:special.append(f'{token:02X}')
    return {'firmware_sha256':SHA,
            'segment_scanner':{'entry':'1:D7D7','boundary':'1:D7F1',
                'pointer':'D861 tag, D862:D863 big-endian address',
                'count':'direct RAM 26h (copied from D842 by caller)',
                'rule':'Skip count FF-terminated segments; leave pointer just after the final skipped FF.',
                'scratch_writes':['D862','D863'],'synthetic_checks':synthetic,
                'actual_code_resource_checks':len(warning),'warning_resource_segments':warning},
            'prefix_classifier':{'entry':'1:D803','checks':256,
                'special_tokens':special,'action':'1:D0AF stores token at D867 and increments direct RAM 28h.',
                'limits':'Classification verified; downstream semantic meaning of each token still needs proof.'},
            'modification_constraint':'Changing a segment length moves later segments; FF bytes delimit the scanner. Preserve/rebuild all affected addresses and segment structure before considering a patch.',
            'limits':['Segment skip tests stop before hardware rendering.',
                      '21 scanned segments fill the interval between two resolved resource pointers; they are not a proven supported/named-language list.',
                      'No hardware writes, language changes, firmware patch or flash.']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('firmware',type=Path)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    result=build(args.firmware.read_bytes())
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print('Verified segment checks:',result['segment_scanner']['synthetic_checks']+result['segment_scanner']['actual_code_resource_checks'])
    print('Verified classifier cases:',result['prefix_classifier']['checks'])


if __name__=='__main__':main()

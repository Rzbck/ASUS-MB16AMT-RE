"""Recover checked DA6B/DA6D callback selection without executing handlers."""
import argparse
import hashlib
import json
from pathlib import Path
from analyze_banked_abi import SHA, inventory, traverse
from emulate_mcs51 import Machine


class Selected(Exception):pass


class Selector(Machine):
    def __init__(self,*args):
        super().__init__(*args);self.selected = None;self.exit_path = False
    def jump(self,target,call=False):
        if target == 0x2133:
            self.selected = (self.r(2)<<8)|self.r(1)
            raise Selected
        if self.bank == 8 and self.origin == 0xE4BC and target == 0xFED6:
            self.exit_path = True
            raise Selected
        super().jump(target,call)


def table(data,bank,base,low,high):
    rows = []
    for setting in range(low,high+1):
        cells = []
        for command in range(4):
            address = base+12*setting+3*command
            pos = bank*65536+address
            assert data[pos] == 255
            target = int.from_bytes(data[pos+1:pos+3],'big')
            cells.append({'command':command,'cell':f'{bank}:{address:04X}',
                          'tag':'FF','target':f'{bank}:{target:04X}'})
        rows.append({'setting':f'{setting:02X}','callbacks':cells})
    return rows


def execute_selection(data,thunks,bank,entry,setting,command):
    m = Selector(data,thunks);m.x[0xDA6B] = setting;m.x[0xDA6D] = command
    try:m.run(bank,entry,budget=100)
    except Selected:pass
    assert {a for _,_,a in m.reads} <= {0xDA6B,0xDA6D}
    if bank == 8:
        assert m.writes == {(8,0xE49E,0xD821)}
    else:assert not m.writes
    return m


def prelude_checks(data,thunks):
    assert thunks[0x1934] == (10,0xFEB0)
    for setting in range(256):
        for old in range(256):
            m = Machine(data,thunks);m.sr(7,old)
            m.x[0xDA6B] = setting;m.x[0xDA83] = old
            m.run(10,0xFEB0,budget=40)
            assert bytes(m.x[0xDBFD:0xDC01]) == bytes((0,0x24,4,8))
            assert m.x[0xDA83] == (7 if setting == 0 else old)
            assert {a for _,_,a in m.writes} == set(range(0xDBFD,0xDC01)) | ({0xDA83} if setting == 0 else set())
            assert {a for _,_,a in m.reads} == {0xDA6B}
    return 65536


def build(data):
    assert len(data) == 0xE0000 and hashlib.sha256(data).hexdigest() == SHA
    thunks = inventory(data)
    normal = table(data,9,0x8FAF,0,0x5D)
    alternate = table(data,8,0x38C0,0x5E,0xA8)
    checks = 0; seeds = set()
    for row in normal:
        setting = int(row['setting'],16)
        for cell in row['callbacks']:
            command = cell['command'];target = int(cell['target'].split(':')[1],16)
            m = execute_selection(data,thunks,9,0xA23E,setting,command)
            assert m.selected == target and not m.exit_path
            # Execute common indirect jump itself, stop before callback body.
            try:m.run(9,0x2133,budget=4)
            except AssertionError as error:
                assert str(error).startswith('Instruction budget exceeded at')
            else:raise AssertionError('Expected callback boundary')
            assert (m.bank,m.pc) == (9,target)
            seeds.add((9,target));checks += 1
    alternate_checks = 0; selected = 0; exit_count = 0
    for setting in range(256):
        for command in range(256):
            m = execute_selection(data,thunks,8,0xE49A,setting,command)
            legal_setting = 0x5E <= setting <= 0xA8
            if legal_setting and command < 4:
                cell = alternate[setting-0x5E]['callbacks'][command]
                target = int(cell['target'].split(':')[1],16)
                assert m.selected == target and not m.exit_path
                seeds.add((8,target));selected += 1
            elif legal_setting and command in (4,5):
                assert m.exit_path and m.selected is None;exit_count += 1
            else:assert m.selected is None and not m.exit_path
            alternate_checks += 1
    # Carry survives the chained SUBB guards: columns0..3, exit4/5, reject>=6.
    original,_,original_indirect,_,_ = traverse(data,thunks)
    decoded,edges,indirect,reserved,overlaps = traverse(data,thunks,extra_seeds=seeds)
    assert not reserved and not overlaps
    assert all(seed in decoded or (seed[1] in thunks and thunks[seed[1]] in decoded) for seed in seeds)
    return {'firmware_sha256':SHA,
            'normal':{'entry':'9:A23E..A26A','base':'9:8FAF','stride':12,'cell_stride':3,
                'checked_setting_range':'00..5D','commands':list(range(4)),
                'checks':checks,'rows':normal,
                'qualification':'No local setting/command bound at A23E; tested range follows the normal/alternate partition and FF-tagged cells. Out-of-range reads are not classified as callbacks.'},
            'alternate':{'entry':'8:E49A..E4EB','base':'8:38C0','guard_setting_range':'5E..A8',
                'checks':alternate_checks,'selected_cases':selected,'common_exit_cases':exit_count,
                'commands':'0..3 select table; 4/5 jump FED6 -> F7D5; >=6 return',
                'rows':alternate,'carry_guard':'Chained SUBB instructions retain carry; do not infer bounds from immediate operands alone.'},
            'indirect_call':'Cells use bytes1/2 as R2:R1; byte0 is not loaded by these callers. Common2133 sets DPTR=R2:R1 and jumps with A=0 in current bank.',
            'graph':{'original_instructions':len(original),'instructions_with_verified_callbacks':len(decoded),
                'new_instruction_starts':len(set(decoded)-set(original)),
                'explicit_callback_seeds':len(seeds),'new_indirect_sites':[f'{b}:{p:04X}' for b,p in sorted(set(indirect)-set(original_indirect))],
                'reserved_opcode_sites':len(reserved),'overlap_sites':len(overlaps)},
            'callback_prelude':{'thunk':'1934 -> 10:FEB0','checks':prelude_checks(data,thunks),'writes':'DBFD..DC00=00,24,04,08; if DA6B=0, DA83=07; otherwise DA83 unchanged. R7 is not consumed on this checked path.'},
            'limits':['Selection/callback addresses are verified in the static bank model; handler bodies are traversed, not functionally proved.',
                'Full dynamic validity, setting names, command labels and upstream gate/lifecycle coverage remain open.',
                'A command outside0..3 can mechanically read another row; this is not promoted to valid normal-table behavior.',
                'Physical firmware-bank identity retains the existing static-model qualification.',
                'No firmware bytes, callback payloads or monitor commands are published.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('firmware',type=Path);parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args();result = build(args.firmware.read_bytes())
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print('Normal/alternate selection checks:',result['normal']['checks'],result['alternate']['checks'])
    print('Callback graph:',result['graph'])


if __name__ == '__main__':main()

"""Verify navigation's DA72 gate release before menu dispatch, offline."""
import argparse
import hashlib
import json
from pathlib import Path
from collections import Counter
from analyze_banked_abi import SHA, inventory
from emulate_mcs51 import Machine


class Selected(Exception):pass


class Navigation(Machine):
    def __init__(self,*args):
        super().__init__(*args);self.selected = None
    def jump(self,target,call=False):
        if self.bank == 9 and self.origin == 0xA1DA and target == 0xA384:
            self.selected = 'state58_return';raise Selected
        if self.bank == 9 and self.origin == 0xA20F and target == 0xFC11:
            self.selected = 'full_release';raise Selected
        super().jump(target,call)
    def readx(self,address):
        if self.bank == 9 and self.origin == 0xA215 and address == 0xDA68:
            self.selected = 'dispatch';raise Selected
        return super().readx(address)


def fixture(data,thunks,state,gate,status,flags):
    m = Navigation(data,thunks);m.x[0xDA6B] = state;m.x[0xDA72] = gate
    m.x[0xDA91] = status;m.x[0xDA50] = flags
    try:m.run(9,0xA1D1,budget=100)
    except Selected:pass
    else:raise AssertionError('Expected verified boundary')
    cleared = state != 0x58 and not 0x53 <= state <= 0x55 and bool(gate&8) and (status == 3 or bool(flags&0x20))
    release = state != 0x58 and not 0x53 <= state <= 0x55 and bool(gate&8) and not cleared
    assert m.selected == ('state58_return' if state == 0x58 else 'full_release' if release else 'dispatch')
    assert m.x[0xDA72] == (gate&0xE7 if cleared else gate)
    assert {a for _,_,a in m.writes} == ({0xDA72} if cleared else set())
    assert m.x[0xDA6B] == state and m.x[0xDA91] == status and m.x[0xDA50] == flags
    return 'direct_clear' if cleared else m.selected


def build(data):
    assert len(data) == 0xE0000 and hashlib.sha256(data).hexdigest() == SHA
    thunks = inventory(data);counts = Counter();checks = 0
    for state in range(256):
        for gate in range(256):
            for status in (0,3):
                for flags in (0,0x20):
                    counts[fixture(data,thunks,state,gate,status,flags)] += 1;checks += 1
    # Verify exact equality-to3 and bit5 extraction across all source bytes.
    fields = 0
    for status in range(256):
        for flags in (0,0x20):
            fixture(data,thunks,0,24,status,flags);fields += 1
    for flags in range(256):
        for status in (0,3):
            fixture(data,thunks,0,24,status,flags);fields += 1
    assert thunks[0x19AC] == (8,0xE49A)
    chunk = data[9*65536:10*65536]
    assert chunk[0xA212:0xA21F] == bytes.fromhex('90 DA 68 E0 FF C3 13 30 E0 03 02 19 AC')
    return {'firmware_sha256':SHA,'gate_state_checks':checks,
            'source_field_checks':fields,'boundary_counts':dict(sorted(counts.items())),
            'entry':'9:A1D1; this is a block within navigation, not its complete entry.',
            'state58':'DA6B=58 jumps9:A384 RET before gate handling or menu dispatch.',
            'protected_states':'DA6B53..55 inclusive bypass gate handling; original flags retained.',
            'gate_clear':'For other states, DA72.bit3 clear bypasses release and retains flags.',
            'direct_clear':'For other states withDA72.bit3 set, DA91=3 orDA50.bit5 set clearsDA72.bits3/4 via9:A203..A20C before dispatch; no FC11 call or other XDATA write in this block.',
            'full_release':'Otherwise9:A20F callsFC11, then continues9:A212. Verifier stops before this callee; complete FC11/deferred-language proof is in map_osd_overlay_gate.',
            'dispatch_link':'9:A212 testsDA68.bit1: set LJMP19AC->8:E49A alternate handler selector; clear continues normal-path guards before known9:A23E selector.',
            'limits':['All execution offline; no hardware operation.',
                      'Preceding navigation gates and physical meanings ofDA91/DA50 flags remain unassigned.',
                      'Exhaustive fixtures at this block do not prove arbitrary DA6B values are legal menu states.',
                      'Direct-clear bypasses FC11 locally; no global claim that pending dirty settings are lost.',
                      'DA68 branch bytes checked statically; normal-path guards afterA21F are not executed by this verifier.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('firmware',type=Path);parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args();result = build(args.firmware.read_bytes())
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print('Navigation state/gate and source-field checks:',result['gate_state_checks'],result['source_field_checks'])


if __name__ == '__main__':main()

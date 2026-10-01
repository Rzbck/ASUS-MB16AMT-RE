"""Verify receive-side language SET offline; stop before refresh callee."""
import argparse
import hashlib
import json
from pathlib import Path
from analyze_banked_abi import SHA, inventory
from emulate_mcs51 import Machine
from map_osd_notifications import LANGUAGE_CODES
from trace_vcp_opcode_switch import parse_switch


class RefreshBoundary(Exception):
    pass


class Setter(Machine):
    def jump(self, target, call=False):
        if self.bank == 9 and self.origin == 0x9CA8 and target == 0x15F8:
            raise RefreshBoundary
        super().jump(target, call)


def fixture(data, thunks, code, old, high=0, dirty=0, gate=8):
    m = Setter(data, thunks)
    m.x[0xD993:0xD996] = bytes((0xCC, high, code))
    m.x[0xDA03] = old;m.x[0xDA69] = dirty;m.x[0xDA72] = gate
    m.x[0xDCC4:0xDCC6] = bytes((0xA5,0x5A));m.sbit(0x25,1)
    reached = False
    try:m.run(9,0x9452,budget=200)
    except RefreshBoundary:reached = True
    inverse = {code:index for index,code in enumerate(LANGUAGE_CODES)}
    expected = (old&0xC0)|inverse[code] if code in inverse else old
    assert m.x[0xDA03] == expected and m.x[0xDA69] == dirty|1
    assert bytes(m.x[0xDCC4:0xDCC6]) == bytes((0xA5,0xCC)) and m.bit(0x25) == 0
    assert reached == (not bool(gate&8))
    reads = {a for _,_,a in m.reads};writes = {a for _,_,a in m.writes}
    assert 0xD994 not in reads and 0xD995 in reads
    assert (0xDA03 in writes) == (code in inverse)
    assert writes <= {0xD820,0xDCC5,0xDA03,0xDA69}
    assert not ({0xDA6C,0xDA87}&writes)
    return reached


def build(data):
    assert len(data) == 0xE0000 and hashlib.sha256(data).hexdigest() == SHA
    thunks = inventory(data);chunk = data[9*65536:10*65536]
    main,_,_ = parse_switch(chunk,0x946B)
    assert next(target for code,target,_ in main if code == 0xCC) == 0x9883
    rows,default,end = parse_switch(chunk,0x988A)
    assert {code for code,_,_ in rows} == set(LANGUAGE_CODES)
    assert (default,end) == (0x997A,0x98CD)
    checks = 0
    for code in range(256):
        for old in range(256):
            fixture(data,thunks,code,old);checks += 1
    high_checks = 0
    for code in range(256):
        for high in range(256):
            fixture(data,thunks,code,0xD4,high=high);high_checks += 1
    dirty_checks = 0
    for code in (0,2,0x31,0xFF):
        for dirty in range(256):
            fixture(data,thunks,code,0xC7,dirty=dirty);dirty_checks += 1
    gate_checks = 0
    for code in (0,2,0x31,0xFF):
        for gate in range(256):
            fixture(data,thunks,code,0xC7,gate=gate);gate_checks += 1
    return {'firmware_sha256':SHA,'code_packed_language_checks':checks,
            'high_payload_checks':high_checks,'dirty_checks':dirty_checks,
            'refresh_gate_checks':gate_checks,
            'dispatch':'9:9452 opcodeD993 ->9:9883 readsD995 ->inline9:988A',
            'mapping':[{'code':f'{code:02X}','index':LANGUAGE_CODES.index(code),
                        'branch':f'9:{target:04X}'} for code,target,_ in rows],
            'unsupported':'Default9:997A retainsDA03 but still ORsDA69 bit0.',
            'packed_write':'Valid codes writeDA03=(old&C0)|index, including unchanged selections.',
            'payload':'D994 is not read on these paths; exhaustive high-byte fixtures give identical effects.',
            'notification':'Prologue writesDCC5=CC and clearsbit25; DCC4 remains unchanged. Unlike OSD FD52, it does not assignDCC4=2.',
            'refresh':'9:D2A3 rotatesDA72 three times and masks1F;9:9CA5 tests resultingbit0, exactly originalDA72 bit3. Clear invokes15F8->10:F439; set returns without it.',
            'limits':['Offline bytearray execution only; no monitor command.',
                      'Clear-bit3 cases stop before10:F439; refresh internals and subsequent event/save execution are not proved here.',
                      'NoDA6C/DA87 write occurs before that boundary or on the complete set-bit3 path.',
                      'DA72 bit3 meaning is not assigned from this branch alone.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('firmware',type=Path);parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args();result = build(args.firmware.read_bytes())
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print('SET code/high/dirty/gate checks:',*(result[k] for k in
          ('code_packed_language_checks','high_payload_checks','dirty_checks','refresh_gate_checks')))


if __name__ == '__main__':main()

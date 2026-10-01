"""Verify navigation fallback, status decoder and complete timer-slot effects offline."""
import argparse
import hashlib
import json
from pathlib import Path
from analyze_banked_abi import SHA, inventory
from emulate_mcs51 import Machine


class Accepted(Exception):pass


class Decision(Machine):
    def jump(self,target,call=False):
        if (self.bank,self.origin,target) == (9,0xA35F,0x0B84):raise Accepted
        super().jump(target,call)


def decision(data,thunks,mode,command,event,status):
    m = Decision(data,thunks);m.x[0xDCB7] = mode;m.x[0xDA6D] = command
    m.x[0xDA6C] = event;m.x[0xDCC9] = status<<4
    accepted = False
    try:m.run(9,0xA334,budget=150)
    except Accepted:accepted = True
    assert accepted == (mode&31 in (4,6) and command<5 and event != 7 and status != 3)
    assert not m.writes


def timer_fixture(data,thunks,mode,first,second,occupied=False,existing=None):
    table = bytearray(48)
    for i in range(16):table[3*i:3*i+3] = bytes((0x20+i if occupied else 0,0x40+i,0x80+i))
    table[3*first] = 13;table[3*second] = 14
    timer = 5 if mode == 4 else 12
    if existing is not None:table[3*existing] = timer
    m = Machine(data,thunks);m.x[0xDCB7] = mode;m.x[0xD92D:0xD95D] = table
    m.run(9,0xA334,budget=10000)
    expected = bytearray(table);expected[3*first] = expected[3*second] = 0
    selected = existing if existing is not None else next(i for i in range(16) if expected[3*i] == 0)
    expected[3*selected:3*selected+3] = bytes((timer,0x13,0x88))
    assert m.x[0xD92D:0xD95D] == expected
    assert m.x[0xDA6C] == 0 and not m.calls and not m.stack
    assert {a for _,_,a in m.writes} <= set(range(0xD825,0xD829))|set(range(0xD82A,0xD831))|set(range(0xD92D,0xD95D))


def build(data):
    assert len(data) == 0xE0000 and hashlib.sha256(data).hexdigest() == SHA
    thunks = inventory(data);status_checks = core = events = slots = existing_checks = 0
    for packed in range(256):
        for secondary in range(256):
            for carry in (0,1):
                m = Machine(data,thunks);m.x[0xDCC9] = packed;m.x[0xDCCA] = secondary;m.c = carry
                result = m.run(7,0xF2FC,budget=60);nibble = packed>>4
                expected = (1 if secondary&64 else 3 if secondary&32 else 2) if nibble == 2 else nibble
                assert result == expected and not m.writes;status_checks += 1
    for raw in range(256):
        for command in range(256):
            for event in (0,7):
                for status in (0,3):
                    decision(data,thunks,raw,command,event,status);core += 1
    for mode in (4,6):
        for event in range(256):
            for command in (0,4,5):
                for status in (0,3):
                    decision(data,thunks,mode,command,event,status);events += 1
        for first in range(16):
            for second in range(16):
                if first == second:continue
                for occupied in (False,True):
                    timer_fixture(data,thunks,mode,first,second,occupied);slots += 1
        for existing in (0,7,15):
            for first,second in ((1,2),(14,13),(3,10)):
                if existing in (first,second):continue
                timer_fixture(data,thunks,mode,first,second,True,existing);existing_checks += 1
        # A full table without canceled IDs or the requested timer stays full.
        m = Machine(data,thunks);m.x[0xDCB7] = mode
        full = b''.join(bytes((0x20+i,0x40+i,0x80+i)) for i in range(16))
        m.x[0xD92D:0xD95D] = full;m.run(9,0xA334,budget=10000)
        assert m.x[0xD92D:0xD95D] == full and m.x[0xDA6C] == 0
    # Cancellation clears only the first matching slot, leaving deadline bytes.
    duplicate = Machine(data,thunks);duplicate.sr(7,13)
    duplicate.x[0xD92D:0xD933] = bytes.fromhex('0D 12 34 0D 56 78')
    duplicate.run(5,0xF920,budget=300)
    assert duplicate.x[0xD92D:0xD933] == bytes.fromhex('00 12 34 0D 56 78')
    leaves = []
    for timer,target,value in ((5,0xECD1,2),(12,0xEF47,9)):
        m = Machine(data,thunks);m.x[0xDA6C] = 0xFF;m.run(4,target,budget=20)
        assert m.x[0xDA6C] == value and {a for _,_,a in m.writes} == {0xDA6C}
        leaves.append({'timer':f'{timer:02X}','writer':f'4:{target:04X}','DA6C':f'{value:02X}'})
    return {'firmware_sha256':SHA,'status_checks':status_checks,'decision_checks':core,
            'all_event_byte_checks':events,'complete_timer_slot_checks':slots,
            'existing_timer_checks':existing_checks,'full_table_checks':2,'duplicate_cancel_checks':1,
            'timer_event_links':leaves,
            'gate':'9:A334 acceptsDCB7&1F in4/6,DA6D<5,DA6C!=7 and186E/7:F2FC result!=3. OtherwiseRET, noXDATAwrite.',
            'status':'F2FC returnsDCC9 high nibble except2: DCCA.bit6 set ->1; elsebit5 set ->3; else2. Low nibble/incomingcarry irrelevant.',
            'accepted':'Cancel timers0D then0E via0B84/5:F920; request0B72/5:E671 R6:R7=1388(5000),R5=05 mode4 or0C mode6. No directDA6C publication.',
            'slots':'Actual cancellation/scheduler executes16 slots atD92D+3*i. Canceled slot IDs clear while deadline bytes remain. Existing requested timer is updated; otherwise first empty slot used. Full table withoutmatching IDs remains unchanged.',
            'qualification':'Complete slot fixtures initialize timing RAM/XDATA tozero and verify deadline1388 only under that snapshot; physical time and interrupts are unmodeled.',
            'limits':['Offline in-memory execution; no hardwarecommand.',
                      'Canceled duplicate test proves firstmatch-only behavior, not that duplicates are valid runtime state.',
                      'Timer leaves checked separately, not through a physical wait or expiration engine.',
                      'Mode/status physical meanings remain unassigned. DA6C7 suppresses this fallback but its full handler meaning remains open.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('firmware',type=Path);parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args();result = build(args.firmware.read_bytes())
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print('Fallback status/decision/slot checks:',result['status_checks'],result['decision_checks'],result['complete_timer_slot_checks'])


if __name__ == '__main__':main()

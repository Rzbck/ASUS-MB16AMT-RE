"""Verify running Timer0/1 conversion during Timer2 mode changes offline."""
import argparse
import hashlib
import json
from pathlib import Path
from analyze_banked_abi import SHA, inventory
from emulate_mcs51 import Machine


def reload_value(rate,previous):
    return (65535-(rate*previous//1000))&65535


def build(data):
    assert len(data) == 0xE0000 and hashlib.sha256(data).hexdigest() == SHA
    thunks = inventory(data);arithmetic = complete = 0
    for rate in (7308,2333):
        for previous in range(65536):
            m = Machine(data,thunks);m.sr(2,rate>>8);m.sr(3,rate&255)
            m.x[0xD98A:0xD98C] = previous.to_bytes(2,'big')
            m.run(5,0xB43E,budget=3000)
            quotient = rate*previous//1000
            assert m.a == 255-(quotient&255) and m.r(6) == (quotient>>8)&255
            assert m.r(7) == quotient&255 and not m.writes
            arithmetic += 1
    for mode in (0,1,2,4):
        for register in (0,4):
            for old in (0,1,2,3):
                for running in range(4):
                    for previous in (0,1,137,1000,65535):
                        m = Machine(data,thunks);m.sr(7,mode);m.x[0xFFED] = register;m.x[0xD928] = old
                        m.sbit(0x8C,running&1);m.sbit(0x8E,running&2);m.sbit(0xA9,1);m.sbit(0xAB,1)
                        m.x[0xD98A:0xD98E] = previous.to_bytes(2,'big')+((previous+1)&65535).to_bytes(2,'big')
                        m.x[0xD982:0xD986] = bytes.fromhex('AB CD 12 34')
                        for high,low,word in ((0xD95D,0xD95F,0x9ABC),(0xD95E,0xD960,0xCDEF)):
                            m.x[high] = word>>8;m.x[low] = word&255
                        m.ram[0x8C] = 0x9A;m.ram[0x8A] = 0xBC
                        m.ram[0x8D] = 0xCD;m.ram[0x8B] = 0xEF
                        m.run(5,0xCA9B,budget=10000)
                        target = 1 if mode == 1 else 3 if register == 4 else 2
                        changed = mode in (1,2) and old != target
                        for timer,mask,backup,prev,high,low,th,tl,initial,current in (
                            (0,1,0xD982,previous,0xD95D,0xD95F,0x8C,0x8A,0xABCD,0x9ABC),
                            (1,2,0xD984,(previous+1)&65535,0xD95E,0xD960,0x8D,0x8B,0x1234,0xCDEF)):
                            active = bool(running&mask)
                            expected = reload_value(7308 if mode == 1 else 2333,prev) if changed and active else initial
                            assert int.from_bytes(m.x[backup:backup+2],'big') == expected
                            applied = expected if active and mode in (1,2) else current
                            assert (m.x[high]<<8|m.x[low]) == applied
                            assert (m.ram[th]<<8|m.ram[tl]) == applied
                        assert m.bit(0x8C) == bool(running&1) and m.bit(0x8E) == bool(running&2)
                        assert m.bit(0xA9) == m.bit(0xAB) == 1
                        assert not m.stack and not m.calls
                        complete += 1
    return {'firmware_sha256':SHA,'arithmetic_checks':arithmetic,'complete_setup_checks':complete,
            'formula':'New backup = (FFFF-floor(rate*previous/1000)) mod65536; rate7308 for mode1,2333 for mode2. Actual common32-bit multiply/divide helpers execute.',
            'sources':'Timer0 previousD98A:D98B ->backupD982:D983; Timer1 previousD98C:D98D ->backupD984:D985.',
            'history_gate':'Conversion only on changedD928 target and initiallyrunningtimer; target1 for mode1,target3/2 for mode2 FFED fragment1/other.',
            'application':'Modes1/2 withtimerinitiallyrunning compare backup to current D95D/D95F(T0) orD95E/D960(T1); changed value copied tothosebytes andTL/TH SFRs, withtimer/interrupt brieflydisabled thenenabled. Stoppedtimer andmodes0/4 retaincurrentbytes.',
            'coverage':'All65536 previouswords for bothrates;640 completefixtures:4modes x2FFED x4histories x4runningmasks x5previouswords.',
            'limits':['Offline bytearray execution only; nohardwaretimer configured.',
                      'Exhaustive arithmetic includes overflow/truncation cases, not proofallpreviouswords are validruntime durations.',
                      'Fullsetup snapshots use fixedinitialbackup/currentvalues; equal-current fastpath and live timer advances are not covered here.',
                      'No physicalclock rate or wall-clock continuity claim; source ofprevious-duration words remainsopen.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('firmware',type=Path);parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args();result = build(args.firmware.read_bytes())
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print('Timer conversion arithmetic/full setup checks:',result['arithmetic_checks'],result['complete_setup_checks'])


if __name__ == '__main__':main()

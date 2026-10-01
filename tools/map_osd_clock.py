"""Verify software-clock ISR and bounded delay coefficient selector offline."""
import argparse
import hashlib
import json
from pathlib import Path
from analyze_banked_abi import SHA, inventory
from emulate_mcs51 import Machine


def irq(data,thunks,clock,mode=0,flags=0,other=0):
    m = Machine(data,thunks);m.ram[0x42:0x44] = clock.to_bytes(2,'big')
    m.a = 0x5A;m.dptr = 0x5432;m.ram[0xD0] = 0xA5;m.ram[0xC8] = 0xFF
    m.x[0xFFF4] = 0xAB;m.x[0xFFAD] = mode;m.x[0xFFEB] = flags;m.x[0xFFEA] = other
    m.run(0,0x2B,budget=80)
    assert int.from_bytes(m.ram[0x42:0x44],'big') == (clock+1)&65535
    assert (m.a,m.dptr,m.ram[0xD0]) == (0x5A,0x5432,0xA5)
    assert m.bit(0xCF) == 0 and m.bit(0x1E) == m.bit(0x1F) == 1
    assert m.x[0xDCA6] == m.x[0xFFF4] == 0xAB
    assert m.x[0xFFEB] == (flags&0x7F)|8
    assert m.x[0xFFEA] == (other|64 if mode&7 >= 5 else other)
    expected = {0xDCA6,0xFFEB,0xFFF4}|({0xFFEA} if mode&7 >= 5 else set())
    assert {a for _,_,a in m.writes} == expected
    assert not m.stack and not m.calls


def build(data):
    assert len(data) == 0xE0000 and hashlib.sha256(data).hexdigest() == SHA
    assert data[0x2B:0x2E] == bytes.fromhex('02 01 40')
    thunks = inventory(data);clock_checks = register_checks = coefficient_checks = 0
    for clock in range(65536):
        irq(data,thunks,clock);clock_checks += 1
    for mode in range(256):
        for flags,other in ((0,0),(0xFF,0xFF),(0x80,0xBF),(0x55,0xAA)):
            irq(data,thunks,0xFFFF,mode,flags,other);register_checks += 1
    for selector in range(256):
        m = Machine(data,thunks);m.sr(7,selector)
        m.ram[0x36] = m.ram[0x39] = 0xAA
        m.run(0,0xFD6C,budget=20)
        assert (m.ram[0x39],m.ram[0x36]) == ((26,21) if selector == 2 else (3,6) if selector == 1 else (2,2))
        assert not m.writes;coefficient_checks += 1
    return {'firmware_sha256':SHA,'whole_ISR_clock_checks':clock_checks,
            'ISR_register_checks':register_checks,'delay_selector_checks':coefficient_checks,
            'vector':'Common002B LJMP0140; entire0140..0189 ISR executes throughRETI.',
            'clock':'0171 incrementsRAM43; zero carry incrementsRAM42 at0177. BE16RAM42:43 advancesone modulo65536 per serviced interrupt.',
            'preservation':'ISR saves/restoresA,DPTR,PSW; retainsFFF4 throughDCA6; clearsSFRbitCF and setsRAMbits1E/1F.',
            'registers':'FFEB=(old&7F)|08; FFEA|=40 only ifFFAD&7>=5. No other XDATAwrites.',
            'delay_selector':'At0:FD6C,R7=2 ->RAM39=26/RAM36=21;R7=1 ->3/6;other ->2/2. Caller/sourceofR7 notprovedhere.',
            'limits':['Offline bytearray execution only; no hardwarecommand or actual interrupt delivery.',
                      'OneincrementperISR is not a measured tickfrequency or millisecond proof.',
                      'Interrupt enable/reload/clock-source setup and calibrationcaller remainopen.',
                      'No AC/OV/parity/interrupt nesting modeled; checked ISR preservesPSW snapshot viaexplicitstack.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('firmware',type=Path);parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args();result = build(args.firmware.read_bytes())
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print('Clock ISR/register/delay selector checks:',result['whole_ISR_clock_checks'],result['ISR_register_checks'],result['delay_selector_checks'])


if __name__ == '__main__':main()

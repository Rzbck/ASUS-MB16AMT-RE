"""Verify software-clock ISR and bounded delay coefficient selector offline."""
import argparse
import hashlib
import json
from pathlib import Path
from analyze_banked_abi import SHA, inventory
from emulate_mcs51 import Machine


class SlotDone(Exception):pass


class Slot(Machine):
    def readx(self,address):
        if (self.bank,self.origin,address) == (5,0xD904,0xD82C):raise SlotDone
        return super().readx(address)


def provenance_checks(data,thunks):
    for bank,pc,expected in ((0,0x6394,'E4 FF 12 FD 5B'),
                             (7,0xD5B9,'7F 02 12 0D 3A'),(7,0xD5F3,'7F 01 12 0D 3A')):
        literal = bytes.fromhex(expected)
        assert data[bank*65536+pc:bank*65536+pc+len(literal)] == literal
    assert thunks[0x0D3A] == (0,0xFD5B)
    coefficient = 0
    for selector in (0,1,2):
        for ffee in range(256):
            for ffed in range(256):
                m = Machine(data,thunks);m.sr(7,selector)
                m.x[0xFFEE] = ffee;m.x[0xFFED] = ffed
                m.run(0,0xFD5B,budget=30)
                assert (m.ram[0x39],m.ram[0x36]) == ((26,21) if selector == 2 else (3,6) if selector == 1 else (2,2))
                assert m.r(5) == (ffee&0x3C)>>2 and m.ram[0xF0] == m.r(5)
                assert {a for _,_,a in m.reads} == {0xFFEE,0xFFED} and not m.writes
                coefficient += 1
    isolated = 0
    for elapsed in (0,1,0x8000,0xFFFF):
        for deadline in range(65536):
            m = Slot(data,thunks);m.x[0xD82D:0xD82F] = elapsed.to_bytes(2,'big')
            m.x[0xD92D:0xD930] = bytes((1,deadline>>8,deadline&255))
            try:m.run(5,0xD8C1,budget=100)
            except SlotDone:pass
            else:raise AssertionError('Expected slot boundary')
            expected = max(deadline-elapsed,0)
            assert int.from_bytes(m.x[0xD92E:0xD930],'big') == expected
            assert m.x[0xD92D] == 1 and {a for _,_,a in m.writes} == {0xD92E,0xD92F}
            isolated += 1
    whole = 0
    values = (0,1,0x7FFF,0x8000,0xFFFE,0xFFFF)
    for elapsed in values:
        for deadline in values:
            for slot in range(16):
                for clock in (0,1,0x5A5A,0xFFFF):
                    m = Machine(data,thunks);m.ram[0x42:0x44] = clock.to_bytes(2,'big');m.sbit(0x1E,1)
                    m.x[0xD82D:0xD82F] = elapsed.to_bytes(2,'big')
                    table = bytearray(bytes.fromhex('00 BE EF')*16)
                    table[slot*3:slot*3+3] = bytes((1,deadline>>8,deadline&255))
                    m.x[0xD92D:0xD95D] = table;m.run(5,0xD893,budget=1000)
                    expected = max(deadline-elapsed,0);table[slot*3+1:slot*3+3] = expected.to_bytes(2,'big')
                    assert m.x[0xD92D:0xD95D] == table
                    assert m.ram[0x42:0x44] == bytes(2) and m.bit(0x1E) == 0
                    assert bytes(m.x[0xD82D:0xD82F]) == bytes(2) and m.r(6) == m.r(7) == 0
                    assert not m.stack and not m.calls
                    whole += 1
    return {'register_independent_coefficient_checks':coefficient,
            'isolated_deadline_checks':isolated,'whole_reset_rebase_checks':whole,
            'callers':[{'site':'0:6396','R7':0},{'site':'7:D5BB','R7':2},{'site':'7:D5F5','R7':1}],
            'coefficient_source':'FD5B readsFFEE/FFED and setsR5/B fromFFEE bits5..2; FD6C still selects coefficients solely from callerR7.',
            'rebase':'5:D893 clearsRAM42:43 andbit1E, iterates16slots: nonzeroID keepsID and deadline=max(olddeadline-BE16D82D:D82E,0); zeroID deadline untouched. ClearsD82D:D82E and returnsR6:R7=0.',
            'limits':['Rebase entered atD893 with explicit elapsedword; upstream decision to reset not proved by these fixtures.',
                      'No ISR interleaving; the bit1E recheck atD89A has no asynchronous producer during execution.',
                      'Coefficient caller mode/physical clock labels and interrupt setup remain unassigned.']}


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
            'provenance':provenance_checks(data,thunks),
            'vector':'Common002B LJMP0140; entire0140..0189 ISR executes throughRETI.',
            'clock':'0171 incrementsRAM43; zero carry incrementsRAM42 at0177. BE16RAM42:43 advancesone modulo65536 per serviced interrupt.',
            'preservation':'ISR saves/restoresA,DPTR,PSW; retainsFFF4 throughDCA6; clearsSFRbitCF and setsRAMbits1E/1F.',
            'registers':'FFEB=(old&7F)|08; FFEA|=40 only ifFFAD&7>=5. No other XDATAwrites.',
            'delay_selector':'At0:FD6C,R7=2 ->RAM39=26/RAM36=21;R7=1 ->3/6;other ->2/2. Three directcaller prefixes and fullFD5B register independence are checked inprovenance.',
            'limits':['Offline bytearray execution only; no hardwarecommand or actual interrupt delivery.',
                      'OneincrementperISR is not a measured tickfrequency or millisecond proof.',
                      'Interrupt enable/reload/clock-source setup and physical caller-mode names remainopen.',
                      'No AC/OV/parity/interrupt nesting modeled; checked ISR preservesPSW snapshot viaexplicitstack.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('firmware',type=Path);parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args();result = build(args.firmware.read_bytes())
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print('Clock ISR/register/delay selector checks:',result['whole_ISR_clock_checks'],result['ISR_register_checks'],result['delay_selector_checks'])


if __name__ == '__main__':main()

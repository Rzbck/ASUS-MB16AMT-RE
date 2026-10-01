"""Verify F73D snapshot guard using explicit offline clock-change injection."""
import argparse
import hashlib
import json
from pathlib import Path
from analyze_banked_abi import SHA, inventory
from emulate_mcs51 import Machine


class Snapshot(Machine):
    def __init__(self,data,thunks,second,third):
        super().__init__(data,thunks);self.second = second;self.third = third;self.copies = 0
    def readx(self,address):
        value = super().readx(address)
        if (self.bank,self.origin,address) == (5,0xF743,0xD82F):
            self.ram[0x42:0x44] = self.second.to_bytes(2,'big')
        return value
    def jump(self,target,call=False):
        if self.bank == 5 and target == 0xB631:
            self.copies += 1
            if self.origin == 0xF75F:self.ram[0x42:0x44] = self.third.to_bytes(2,'big')
        super().jump(target,call)


def changed(data,thunks,first,delta):
    second = (first+delta)&65535;third = 0x5A5A
    m = Snapshot(data,thunks,second,third);m.ram[0x42:0x44] = first.to_bytes(2,'big')
    m.run(5,0xF73D,budget=100)
    distance = min(delta,65536-delta)
    recopy = 127<distance<32768
    assert m.copies == (2 if recopy else 1)
    assert m.r(6)*256+m.r(7) == (third if recopy else first)
    assert {a for _,_,a in m.writes} == {0xD82F,0xD830}
    assert not m.calls and not m.stack
    return recopy


def build(data):
    assert len(data) == 0xE0000 and hashlib.sha256(data).hexdigest() == SHA
    thunks = inventory(data);stable = injected = edges = 0;recopies = 0
    for clock in range(65536):
        m = Machine(data,thunks);m.ram[0x42:0x44] = clock.to_bytes(2,'big')
        m.run(5,0xF73D,budget=100)
        assert m.r(6)*256+m.r(7) == clock
        assert {a for _,_,a in m.writes} == {0xD82F,0xD830};stable += 1
    for delta in range(65536):
        recopies += changed(data,thunks,0,delta);injected += 1
    for first in (0,127,255,32768,65535):
        for delta in (0,1,127,128,32767,32768,32769,65408,65409,65535):
            changed(data,thunks,first,delta);edges += 1
    return {'firmware_sha256':SHA,'stable_clock_checks':stable,'injected_delta_checks':injected,
            'wrap_edge_checks':edges,'recopy_delta_count':recopies,
            'contract':'F73D copiesRAM42:43 toD82F:D830; computes signed16-bit difference againstlaterRAMclock, calls002E absolute helper, and recopies once if signedabsolute>127. ReturnR6:R7 is retainedorrecopied scratchword.',
            'edge':'Delta8000 has signedabsolute overflow and doesnotrecopy. Allother signed-distances128..32767 recopy; distances0..127 do not.',
            'one_recapture':'Onrecopy, controlled thirdclock5A5A is returned evenwhenitdiffersfromsecond; nosecondcomparison/retryloop.',
            'injection':'Afteroriginal initialcopy, readx at5:F743 injectssecondclock; before5:F75F recopy call injectsthirdclock. Original instructions andcopyhelpers are notskipped.',
            'limits':['Offline only; nointerrupt delivered orhardwarecommand.',
                      'Whole-word controlledinjection doesnotmodel byte-tearing, IRQnesting orrealtime rates.',
                      'A guard againstlarge read differences is not a proof ofatomic/coherent reads underallinterleavings.',
                      'Delta8000 is mechanicaledgecoverage, not evidence itoccurs in normal firmwareoperation.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('firmware',type=Path);parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args();result = build(args.firmware.read_bytes())
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print('Snapshot stable/injected/edge checks:',result['stable_clock_checks'],result['injected_delta_checks'],result['wrap_edge_checks'])


if __name__ == '__main__':main()

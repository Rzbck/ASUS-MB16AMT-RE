"""Verify clock-reset decision and complete static-clock rebasing calls offline."""
import argparse
import hashlib
import json
from pathlib import Path
from analyze_banked_abi import SHA, inventory
from emulate_mcs51 import Machine


class Done(Exception):pass


class Decision(Machine):
    def __init__(self,*args):
        super().__init__(*args);self.reset = None
    def jump(self,target,call=False):
        if (self.bank,self.origin,target) == (5,0xD890,0xD911):
            self.reset = False;raise Done
        super().jump(target,call)
    def writex(self,address,value):
        super().writex(address,value)
        if (self.bank,self.origin,address) == (5,0xD8A5,0xD82C):
            self.reset = True;raise Done


def decision(data,thunks,argument,clock):
    m = Decision(data,thunks);m.x[0xD82A:0xD82C] = argument.to_bytes(2,'big')
    m.x[0xD82D:0xD82F] = clock.to_bytes(2,'big');m.ram[0x42:0x44] = clock.to_bytes(2,'big')
    try:m.run(5,0xD853,budget=200)
    except Done:pass
    else:raise AssertionError('Expected decision boundary')
    effective = min(argument,61000);reset = clock+effective>61000
    assert int.from_bytes(m.x[0xD82A:0xD82C],'big') == effective
    assert m.reset == reset
    assert int.from_bytes(m.ram[0x42:0x44],'big') == (0 if reset else clock)


def build(data):
    assert len(data) == 0xE0000 and hashlib.sha256(data).hexdigest() == SHA
    thunks = inventory(data);arguments = clocks = complete = 0
    for argument in range(65536):
        for clock in (0,61000,65535):
            decision(data,thunks,argument,clock);arguments += 1
    for clock in range(65536):
        for argument in (0,1,61000):
            decision(data,thunks,argument,clock);clocks += 1
    values = (0,1,127,128,32767,32768,60999,61000,61001,65535)
    for argument in values:
        for clock in values:
            for slot in (0,7,15):
                m = Machine(data,thunks);m.sr(6,argument>>8);m.sr(7,argument&255)
                m.ram[0x42:0x44] = clock.to_bytes(2,'big')
                table = bytearray(bytes.fromhex('00 BE EF')*16)
                table[3*slot:3*slot+3] = bytes.fromhex('01 EA 60')
                m.x[0xD92D:0xD95D] = table;m.run(5,0xD83F,budget=2000)
                reset = clock+min(argument,61000)>61000
                result = 0 if reset else clock
                assert int.from_bytes(m.ram[0x42:0x44],'big') == result
                assert m.r(6)*256+m.r(7) == result
                if reset:table[3*slot+1:3*slot+3] = max(60000-clock,0).to_bytes(2,'big')
                assert m.x[0xD92D:0xD95D] == table and not m.calls and not m.stack
                complete += 1
    return {'firmware_sha256':SHA,'argument_sweep_checks':arguments,
            'clock_sweep_checks':clocks,'complete_static_clock_checks':complete,
            'contract':'5:D83F receivesR6:R7 argument; snapshotclock viaF73D; effective=min(argument,61000). Reset/rebase iff snapshotclock+effective>61000 using unbounded sum; return0 afterreset, snapshotclock otherwise.',
            'implementation':'D853..D864 clampsargument; D865..D877 testswrapped16-bit sumagainst61000; D879..D88E detectswrap. Combined condition matchesunbounded sumthreshold.',
            'equality':'Sum61000 doesnotreset. Argumentabove61000 clamped, so withclock0 evenFFFF argumentdoesnotreset.',
            'rebase':'Onreset, existing16-slot rebase subtractssnapshotclock withsaturation whilepreservingactiveIDs/emptydeadlines.',
            'limits':['Offlineonly, nohardwarecommand.',
                      'F73D executeswithstableRAM42:43; ISRinterleaving andsnapshot retry/stability semantics remainopen.',
                      '61000 is a counter-unitthreshold, not a measured61-second interval.',
                      'Wholefixtures useoneactive slotat0/7/15 andotherwiseempty slots; completeall-slot transformation verified separately bymap_osd_clock.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('firmware',type=Path);parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args();result = build(args.firmware.read_bytes())
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print('Reset argument/clock/whole checks:',result['argument_sweep_checks'],result['clock_sweep_checks'],result['complete_static_clock_checks'])


if __name__ == '__main__':main()

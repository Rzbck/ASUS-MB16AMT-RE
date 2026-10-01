"""Verify mode/command, timer and normal-dispatch navigation gates offline."""
import argparse
import hashlib
import json
from pathlib import Path
from collections import Counter
from analyze_banked_abi import SHA, inventory
from emulate_mcs51 import Machine


class Boundary(Exception):pass


class Guard(Machine):
    def __init__(self,*args):
        super().__init__(*args);self.selected = None;self.timer = None
    def jump(self,target,call=False):
        site = (self.bank,self.origin,target)
        names = {(9,0xA19D,0xA384):'early_return',
                 (9,0xA1BB,0xA334):'fallback',
                 (9,0xA1C6,0xA334):'fallback',
                 (9,0xA1CE,0xA334):'fallback',
                 (9,0xA23B,0x1640):'state5D_transition'}
        if site in names:
            self.selected = names[site];raise Boundary
        if site == (9,0xA16C,0x0B7E):
            self.selected = 'timer';self.timer = (self.r(6)*256+self.r(7),self.r(5));raise Boundary
        super().jump(target,call)
    def readx(self,address):
        if (self.bank,self.origin,address) == (9,0xA1D4,0xDA6B):
            self.selected = 'overlay_block';raise Boundary
        if (self.bank,self.origin,address) == (9,0xA241,0xDA6B):
            self.selected = 'normal_selector';raise Boundary
        return super().readx(address)
    def writex(self,address,value):
        super().writex(address,value)
        if (self.bank,self.origin,address) in ((9,0xA17E,0xD820),(9,0xA183,0xD820)) and self.selected == 'timer_guard':
            self.selected = 'no_timer';raise Boundary


def run_boundary(m,entry):
    try:m.run(9,entry,budget=150)
    except Boundary:pass
    else:raise AssertionError('Expected checked block boundary')


def command_fixture(data,thunks,raw,command,state,flags,dc77):
    m = Guard(data,thunks);m.x[0xDCB7] = raw;m.x[0xDA6D] = command
    m.x[0xDA6B] = state;m.x[0xDA68] = flags;m.x[0xDC77] = dc77
    run_boundary(m,0xA16F)
    mode = raw&31;limit = 6 if flags&2 else 5;accepted = command<limit
    if mode == 5 and dc77 and accepted and state != 5:expected = 'early_return'
    elif accepted and (mode == 3 or mode in (5,8) and state == 5):expected = 'overlay_block'
    else:expected = 'fallback'
    assert m.selected == expected and m.x[0xD820] == limit
    assert {a for _,_,a in m.writes} == {0xD820}
    return expected


def timer_fixture(data,thunks,raw,da4e,fe0b,da92,word=0):
    m = Guard(data,thunks);m.selected = 'timer_guard'
    m.x[0xDCB7] = raw;m.x[0xDA4E] = da4e;m.x[0xFE0B] = fe0b;m.x[0xDA92] = da92
    m.x[0xDA5E:0xDA60] = word.to_bytes(2,'big')
    run_boundary(m,0xA129)
    eligible = raw&31 in (1,5,6) and not da4e&16 and fe0b == 0 and bool(da92&4)
    assert m.selected == ('timer' if eligible else 'no_timer')
    assert m.timer == (((word+500)&65535,0x16) if eligible else None)
    assert {a for _,_,a in m.writes} == (set() if eligible else {0xD820})
    return eligible


def build(data):
    assert len(data) == 0xE0000 and hashlib.sha256(data).hexdigest() == SHA
    thunks = inventory(data);compare = commands = timer_gate = timer_word = normal = 0
    counts = Counter()
    for limit in range(256):
        for command in range(256):
            m = Machine(data,thunks);m.x[0xD820] = limit;m.x[0xDA6D] = command
            m.run(9,0xAB44,budget=20)
            assert m.c == (command<limit) and m.a == (command-limit)&255 and not m.writes
            compare += 1
    for raw in range(32):
        for command in range(256):
            for state in (0,5,0x56,0x58):
                for flags in (0,2):
                    for dc77 in (0,1):
                        counts[command_fixture(data,thunks,raw,command,state,flags,dc77)] += 1;commands += 1
    raw_checks = 0
    for raw in range(256):
        for command in range(8):
            for state in (0,5):
                for flags in (0,2):
                    command_fixture(data,thunks,raw,command,state,flags,1);raw_checks += 1
    for raw in range(256):
        for da4e in (0,16):
            for fe0b in (0,1):
                for da92 in (0,4):
                    timer_fixture(data,thunks,raw,da4e,fe0b,da92);timer_gate += 1
    for source in range(256):
        timer_fixture(data,thunks,1,source,0,4)
        timer_fixture(data,thunks,1,0,source,4)
        timer_fixture(data,thunks,1,0,0,source)
        timer_gate += 3
    for word in range(65536):
        timer_fixture(data,thunks,1,0,0,4,word);timer_word += 1
    for setting in range(256):
        for da00 in range(256):
            for bit in (0,1):
                m = Guard(data,thunks);m.x[0xDA6B] = setting;m.x[0xDA00] = da00;m.sbit(0x1C,bit)
                run_boundary(m,0xA21F)
                special = bool(da00&4) and setting == 0 and not bit
                assert m.selected == ('state5D_transition' if special else 'normal_selector')
                assert not m.writes
                if special:assert m.r(7) == 0x5D
                normal += 1
    return {'firmware_sha256':SHA,'comparison_checks':compare,'command_mode_checks':commands,
            'raw_mode_checks':raw_checks,'command_boundary_counts':dict(sorted(counts.items())),
            'timer_gate_checks':timer_gate,'timer_word_checks':timer_word,'normal_guard_checks':normal,
            'comparison':'9:AB44 comparesDA6D againstD820; carry means unsignedcommand<threshold.',
            'threshold':'9:A16F setsD820=6 whenDA68.bit1 set, else5. 1532/7:FED0 returnsDCB7&1F through7:E873.',
            'command_gate':'Mode5 +DC77nonzero +command<threshold +setting!=5 returns early. Otherwisecommand<threshold and(mode3 OR mode5/8 withsetting5) reachesA1D1 overlay-release block. Other combinations goA334 fallback.',
            'timer_gate':'9:A129 requests0B7E/5:E77F iffDCB7&1F is1/5/6,DA4E.bit4 clear,FE0B=0,DA92.bit2 set;R5event16,R6:R7=(BE16DA5E:DA5F+500)mod65536.',
            'normal_guard':'9:A21F transitions1640/10:AD44 withR7=5D iffDA00.bit2 set,DA6B=0 anddirectbit1C clear. 19A0/12:FEFB returnsbit1C ascarry. Otherwise reachesknownA23E normal callback selector.',
            'limits':['Offline actual helper instructions; no hardware command.',
                      'Boundaries stop before timer scheduler, fallbackA334, overlay blockA1D1, callback selection body andstate5D transition.',
                      'Command coverage uses32 masked modes, allcommands andfoursettingfixtures; raw mode high bits checked separately. Not everysetting/mode pair.',
                      'Timer500 is an argument increment, not a measured wall-clock delay; unmodeled clock/interrupt effects excluded.',
                      'Physical meanings ofDCB7 modes,DC77,DA4E/DA92 andbit1C remain unassigned; not a full navigation entry proof.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('firmware',type=Path);parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args();result = build(args.firmware.read_bytes())
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print('Navigation comparison/commands/timer/normal checks:',*(result[k] for k in
          ('comparison_checks','command_mode_checks','timer_word_checks','normal_guard_checks')))


if __name__ == '__main__':main()

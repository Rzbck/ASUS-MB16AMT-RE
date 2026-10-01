"""Verify input-to-OSD command publication and repeat timer contracts offline."""
import argparse
import hashlib
import json
from pathlib import Path
from analyze_banked_abi import SHA, inventory
from emulate_mcs51 import Machine


class Boundary(Exception):pass


class Commands(Machine):
    def __init__(self,*args):
        super().__init__(*args);self.schedule = None;self.gate = None

    def jump(self,target,call=False):
        if self.bank == 2 and self.origin == 0xFA62 and target == 0x0B7E:
            self.schedule = ((self.r(6)<<8)|self.r(7),self.r(5))
            raise Boundary
        if self.bank == 2 and (
                target in (0xDEF9,0xDDF0,0xDE3D,0xDE95) or
                self.origin in (0xDDA7,0xDD7B)):
            self.gate = self.origin if self.origin in (0xDDA7,0xDD7B) else target
            raise Boundary
        super().jump(target,call)


def dispatch_checks(data, thunks):
    cases = {4:0xDDA7,8:0xDDF0,16:0xDE3D,32:0xDE95,128:0xDD7B}
    for value in range(65536):
        m = Commands(data,thunks);m.sr(6,value>>8);m.sr(7,value&255)
        try:m.run(2,0xDD54,budget=30)
        except Boundary:pass
        else:raise AssertionError('Expected translation branch boundary')
        assert m.gate == cases.get(value,0xDEF9)
        assert not m.writes
    return 65536


def repeat_model(mask,current,previous,command,flags):
    if (current^previous)&mask:return command,flags|16,None
    flags = flags & ~8 if mask in (2,64) else flags|8
    if not flags&8:return None,flags,None
    if flags&4:return command,flags,None
    return None,flags,(500 if flags&16 else 20,1)


def check_repeat(data,thunks,mask,current,previous,command,flags):
    m = Commands(data,thunks)
    m.sr(6,mask>>8);m.sr(7,mask&255);m.sr(5,command)
    m.x[0xDC9E:0xDCA2] = current.to_bytes(2,'big')+previous.to_bytes(2,'big')
    m.x[0xDA6D] = 0xA5;m.x[0xDA6E] = flags
    try:m.run(2,0xF9FB,budget=100)
    except Boundary:assert m.schedule is not None
    result,new_flags,schedule = repeat_model(mask,current,previous,command,flags)
    assert m.x[0xDA6D] == (0xA5 if result is None else result)
    assert m.x[0xDA6E] == new_flags
    assert m.schedule == schedule
    assert {a for _,_,a in m.writes} <= {0xDA6D,0xDA6E}
    assert {a for _,_,a in m.reads} <= set(range(0xDC9E,0xDCA2)) | {0xDA6E}


def repeat_checks(data,thunks):
    checks = 0
    # Every mask word, with a full masked rising change (zero remains zero).
    for mask in range(65536):
        check_repeat(data,thunks,mask,mask,0,3,0);checks += 1
    # All flag bytes/command0..7 with representative masks and histories.
    for mask in (0,2,4,8,16,32,64,128,5,255,256,65535):
        for current,previous in ((mask,mask),(0,mask),(mask,65535)):
            for command in range(8):
                for flags in range(256):
                    check_repeat(data,thunks,mask,current,previous,command,flags)
                    checks += 1
    # Unrelated changed bits must not publish the command.
    for mask in (4,8,16,32,128):
        for bit in range(16):
            check_repeat(data,thunks,mask,mask,mask^(1<<bit),2,4)
            checks += 1
    return checks


def timer_checks(data,thunks):
    for old in range(256):
        m = Machine(data,thunks);m.sr(7,1);m.x[0xDA6E] = old
        m.run(4,0xEC1F,budget=40)
        assert m.x[0xDA6E] == old|4
        assert {a for _,_,a in m.writes} == {0xDA6E}
    # Actual scheduler execution, fixed synthetic software clocks; no interrupts.
    scheduler_checks = 0
    for period in (20,500):
        for clock in (0,1,10000,60000):
            for free_slot in range(16):
                m = Machine(data,thunks)
                for slot in range(16):
                    m.x[0xD92D+3*slot] = 2 if slot < free_slot else 0
                m.ram[0x42:0x44] = clock.to_bytes(2,'big')
                m.sr(6,period>>8);m.sr(7,period&255);m.sr(5,1)
                before = bytes(m.x[0xD92D:0xD95D])
                m.run(5,0xE77F,budget=10000)
                expected = bytearray(before)
                expected[3*free_slot:3*free_slot+3] = bytes((1,))+((clock+period)&65535).to_bytes(2,'big')
                assert bytes(m.x[0xD92D:0xD95D]) == expected
                scheduler_checks += 1
    # Existing event1 is left unchanged; no free slot is also a no-op.
    for slot in range(16):
        m = Machine(data,thunks);m.sr(7,20);m.sr(5,1)
        m.x[0xD92D+3*slot:0xD930+3*slot] = bytes((1,0x12,0x34))
        before = bytes(m.x[0xD92D:0xD95D]);m.run(5,0xE77F,budget=10000)
        assert bytes(m.x[0xD92D:0xD95D]) == before
        scheduler_checks += 1
    full = Machine(data,thunks);full.sr(7,20);full.sr(5,1)
    for slot in range(16):full.x[0xD92D+3*slot] = 2
    before = bytes(full.x[0xD92D:0xD95D]);full.run(5,0xE77F,budget=10000)
    assert bytes(full.x[0xD92D:0xD95D]) == before
    scheduler_checks += 1
    cancel_checks = 0
    for slot in range(16):
        m = Machine(data,thunks);m.sr(7,1)
        for prior in range(slot):m.x[0xD92D+3*prior] = 2
        m.x[0xD92D+3*slot:0xD930+3*slot] = bytes((1,0x12,0x34))
        before = bytearray(m.x[0xD92D:0xD95D]);before[3*slot] = 0
        m.run(5,0xF920,budget=500)
        assert bytes(m.x[0xD92D:0xD95D]) == before
        cancel_checks += 1
    return {'flag_checks':256,'scheduler_checks':scheduler_checks,'cancel_checks':cancel_checks,
            'timer1':'4:EC1F event01 -> 4:ECA3 ORs DA6E with 04',
            'scheduler':'0B7E -> 5:E77F: sixteen 3-byte slots D92D..D95C; event byte then BE16 deadline',
            'fixture_deadline':'First free slot gets event01 and fixed software clock RAM42:43 + period for tested clocks/periods.',
            'existing_or_full':'Existing event01 is not rescheduled; all occupied by event02 yields no slot update.',
            'cancel':'0B84 -> 5:F920 clears the first matching event byte; leaves its deadline intact.'}


def release_checks(data, thunks):
    class Cancel(Machine):
        def jump(self,target,call=False):
            if (self.bank,self.origin,target) == (2,0xDF05,0x0B84):
                assert self.r(7) == 1
                raise Boundary
            super().jump(target,call)
    for old in range(256):
        m = Cancel(data,thunks);m.x[0xDA6E] = old
        try:m.run(2,0xDEF9,budget=30)
        except Boundary:pass
        else:raise AssertionError('Expected timer cancel boundary')
        assert m.x[0xDA6E] == old & ~12
        assert {a for _,_,a in m.writes} == {0xDA6E}
    return 256


def translation_checks(data,thunks):
    class Translation(Machine):
        def __init__(self,*args):
            super().__init__(*args);self.translated = None
        def jump(self,target,call=False):
            if self.bank == 2 and target == 0xF9FB:
                self.translated = ((self.r(6)<<8)|self.r(7),self.r(5))
                raise Boundary
            super().jump(target,call)
    checks = 0
    for state in (3,4,6):
        for setting in (0,1,3,4,5,0x59,0x5D):
            for mask in (4,8,16,32,128):
                m = Translation(data,thunks)
                m.sr(6,0);m.sr(7,mask)
                m.x[0xDC9E:0xDCA0] = mask.to_bytes(2,'big')
                m.x[0xDCB7] = state;m.x[0xDA6B] = setting
                m.x[0xDA0A:0xDA0E] = bytes((0xAB,3,4,5))
                m.x[0xDA68] = 0x25;m.x[0xDA70] = 255;m.x[0xDA6D] = 0xA5
                # D9FD.bit1=0 and DA09 high nibble=0 fixtures.
                try:m.run(2,0xDD54,budget=500)
                except Boundary:assert m.translated is not None
                if setting == 0x59 and mask in (4,8):
                    assert m.translated is None and m.x[0xDA6D] == 7
                else:
                    command = {4:2,8:1,16:3,32:0,128:0}[mask]
                    if setting == 0x59 and mask in (16,32):command = 1 if mask==16 else 2
                    if setting == 0x5D and mask in (4,8,16,32):command = {4:7,8:7,16:1,32:2}[mask]
                    if setting == 1 and mask == 32:command = 1
                    assert m.translated == (mask,command)
                    assert m.x[0xDA6D] == 0xA5
                category = {4:4,8:5,32:3}.get(mask,11) if setting == 1 else 11
                assert m.x[0xDA0A] == 0xA0|category
                assert m.x[0xDA68] == (0x65 if mask == 128 and setting in (3,4,5) else 0x25)
                assert m.x[0xDA70] == (0xEF if setting == 0x59 and mask in (16,32) else 255)
                assert {a for _,_,a in m.writes} <= {0xDA0A,0xDA68,0xDA70,0xDA6D}
                checks += 1
    return checks


def build(data):
    assert len(data) == 0xE0000 and hashlib.sha256(data).hexdigest() == SHA
    thunks = inventory(data)
    return {'firmware_sha256':SHA,'dispatch_checks':dispatch_checks(data,thunks),
            'DD54_initial_branches':{'0004':'2:DDA7','0008':'2:DDF0','0010':'2:DE3D','0020':'2:DE95','0080':'2:DD7B','otherwise':'2:DEF9'},
            'translation_checks':translation_checks(data,thunks),
            'translation_fixture':'DCB7&1F=3/4/6, D9FD.bit1=0, DA09 high nibble0; DA6B=00/01/03/04/05/59/5D',
            'ordinary_translation':{'0004':2,'0008':1,'0010':3,'0020':0,'0080':0},
            'special_translation':['Setting59: inputs4/8 store DA6D=7 directly; 16/32 translate to1/2 and clear DA70.bit4 in these fixtures.',
                                   'Setting5D: inputs4/8 translate to7, 16/32 to1/2.',
                                   'Setting01: input32 translates to1; inputs4/8/32 replace DA0A low nibble from DA0C/DA0D/DA0B respectively.',
                                   'Input128 sets DA68.bit6 for settings03/04/05.'],
            'repeat_checks':repeat_checks(data,thunks),
            'producer':'2:F9FB: R6:R7 mask, R5 command; current DC9E:DC9F, previous DCA0:DCA1',
            'changed':'If ((current XOR previous) AND mask)!=0: DA6D=command; DA6E|=10; return without scheduling.',
            'unchanged':'Exact masks0002/0040 clear DA6E.bit3; all others set it. If bit3 clear, return. If bit2 set, DA6D=command. Otherwise schedule event01 for 500 if bit4 set, else20.',
            'timer':timer_checks(data,thunks),'release_checks':release_checks(data,thunks),
            'release':'DD54 default -> DEF9 clears DA6E bits2/3, then requests timer01 cancellation.',
            'limits':['Offline synthetic state/software clocks; no device writes or measured repeat period.',
                      'Repeat producer code is checked; this does not prove the full menu-consumer cadence or flag lifecycle.',
                      'Initial DD54 translation branches are exhaustive; their mode/setting-dependent bodies remain to be mapped.',
                      'DA6D command semantics, physical button labels and menu handlers remain incomplete.',
                      'Timer units have primary-reference corroboration elsewhere, but these fixtures prove only argument/deadline arithmetic.',
                      'Scheduler checks use sixteen placements, two periods and four clocks below the wrap threshold; overflow/rescheduling policies are not fully covered.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('firmware',type=Path);parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args();result = build(args.firmware.read_bytes())
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print('Dispatch/repeat/release:',result['dispatch_checks'],result['repeat_checks'],result['release_checks'])
    print('Timer checks:',result['timer'])


if __name__ == '__main__':main()

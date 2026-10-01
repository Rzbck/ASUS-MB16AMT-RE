"""Check language callback gates, setter exclusion and DA49 update provenance."""
import argparse
import hashlib
import json
from pathlib import Path
from analyze_banked_abi import SHA, inventory
from emulate_mcs51 import Machine
from map_osd_storage import StorageMachine, expected_pages


class Boundary(Exception):pass


class Language(Machine):
    def __init__(self,*args):
        super().__init__(*args);self.navigation = False;self.post_update = False
    def jump(self,target,call=False):
        if self.bank == 9 and target == 0xC031:
            self.navigation = True
            raise Boundary
        if (self.bank,self.origin,target) == (9,0xC6C2,0x167C):
            self.post_update = True
            raise Boundary
        super().jump(target,call)


def preview_checks(data,thunks):
    class Preview(Machine):
        def jump(self,target,call=False):
            if (self.bank,self.origin,target) == (9,0xE831,0x19DC):
                raise Boundary
            super().jump(target,call)
    checks = 0
    # Row56 columns0/1/2 are the confirmed apply/preview roots, including alias.
    for command,target in ((0,0xC63A),(1,0xE7F9),(2,0xFEEB)):
        pos = 9*65536+0x8FAF+12*0x56+3*command
        assert data[pos] == 255 and int.from_bytes(data[pos+1:pos+3],'big') == target
    for staged in range(21):
        for command,entry in ((1,0xE7F9),(2,0xFEEB)):
            for stored in range(256):
                m = Preview(data,thunks)
                m.x[0xDA6B] = 0x56;m.x[0xDA6D] = command
                m.x[0xDA49] = staged;m.x[0xDA03] = stored
                try:m.run(9,entry,budget=500)
                except Boundary:pass
                else:raise AssertionError('Expected preview refresh boundary')
                result = (staged+(1 if command == 1 else -1))%21
                assert bytes(m.x[0xDA48:0xDA4A]) == result.to_bytes(2,'big')
                assert bytes(m.x[0xDA54:0xDA56]) == result.to_bytes(2,'big')
                assert m.x[0xDA03] == stored and m.x[0xDA69] == 0
                assert (m.r(7),m.r(5)) == (0x56,result)
                assert {a for _,_,a in m.writes} <= set(range(0xD822,0xD829)) | {0xDA48,0xDA49,0xDA54,0xDA55}
                checks += 1
    return checks


def save_event_checks(data,thunks):
    class Applied(StorageMachine):
        def jump(self,target,call=False):
            if (self.bank,self.origin,target) == (9,0xC6C5,0xAAD9):
                raise Boundary
            super().jump(target,call)
    checks = 0
    for language in range(21):
        for high in (0,64,128,192):
            for flags in (0,8):
                for profile in range(4):
                    m = Applied(data,thunks)
                    m.x[0xD9FD] = 1;m.x[0xD9FE] = profile<<2
                    m.x[0xDA87] = flags;m.x[0xDA6B] = 0x56
                    m.x[0xDA03] = high|((language+1)%21);m.x[0xDA49] = language
                    try:m.run(9,0xC6B0,budget=150)
                    except Boundary:pass
                    else:raise AssertionError('Expected after-event apply boundary')
                    assert m.x[0xDA03] == high|language
                    assert (m.x[0xDA69],m.x[0xDA6C]) == (1,11)
                    assert not m.calls and not m.frames
                    m.run(9,0xB8B2,budget=30000)
                    assert (m.x[0xDA69],m.x[0xDA6C]) == (0,0)
                    assert m.x[0xDA03] == high|language
                    offset = 0x32+36*profile if flags&8 else 0x0E
                    assert [(f['address'],f['count'],f['slave']) for f in m.frames] == expected_pages(offset,36)
                    payload = b''.join(f['payload'] for f in m.frames)
                    assert payload == bytes(m.x[0xD9FD:0xDA21])
                    assert payload[6] == high|language
                    assert m.pin == [v for _ in m.frames for v in (0,1)]
                    assert not m.calls
                    checks += 1
    failures = []
    for failure in ('initial','completion','poll'):
        m = Applied(data,thunks,failure=failure)
        m.x[0xD9FD] = 1;m.x[0xDA03] = 16;m.x[0xDA49] = 17
        try:m.run(9,0xC6B0,budget=150)
        except Boundary:pass
        assert (m.x[0xDA69],m.x[0xDA6C]) == (1,11)
        m.run(9,0xB8B2,budget=500000)
        assert (m.x[0xDA69],m.x[0xDA6C],m.x[0xDA03]) == (0,0,17)
        assert len(m.frames) == 1 and m.pin == [0,1]
        failures.append(failure)
    class Dirty(Machine):
        def __init__(self,*args):
            super().__init__(*args);self.dispatched = []
        def jump(self,target,call=False):
            if self.bank == 9 and target in (0x15C2,0x15EC,0x19BE,0x15F2,0x15E6):
                self.dispatched.append((target,self.x[0xDA69]))
                return  # Explicit boundary model; leaf effects excluded.
            super().jump(target,call)
    for flags in range(256):
        m = Dirty(data,thunks);m.x[0xDA69] = flags;m.x[0xDA6C] = 11
        m.run(9,0xBA6E,budget=250)
        expected = [];remaining = flags
        for bit,target in ((0,0x15C2),(2,0x15EC),(3,0x19BE),(5,0x15F2),(1,0x15E6)):
            if remaining & (1<<bit):
                remaining &= ~(1<<bit);expected.append((target,remaining))
        assert m.dispatched == expected
        assert m.x[0xDA69] == flags&0xD0 and m.x[0xDA6C] == 0
    return {'language_save_checks':checks,'flag_dispatch_checks':256,'failed_save_checks':len(failures),
            'chain':'9:C6B0 -> A93F dirty bit0 ->167C/8:E7E4 DA6C0B ->9:B8B2/BA6E clear dirty bit0 ->15C2/8:DDB3 validator ->01D0 page/FIFO writer ->9:BAE1 clears DA6C.',
            'payload':'Applied DA03 survives validator and occupies source-block byte6 in every page-concatenated payload.',
            'coverage':'All21 indices x four DA03 high-bit combinations x two DA87.bit3 states x four profiles; all256 dirty flags separately at modeled leaf boundaries.',
            'dispatch_order':'BA6E clears bits before leaf calls in order0/2/3/5/1 ->15C2/15EC/19BE/15F2/15E6. Bits4/6/7 are retained by this handler itself.',
            'save_failure':'For initial/completion/poll timeout fixtures, BA6E still leaves DA69.bit0=0 and DA6C=0 while changed DA03 remains in RAM. It clears the dirty bit before15C2 and does not test returned carry; no retry is issued within this handler.',
            'qualification':'Language bit0 fixtures execute real validation/page/frame/poll instructions with synthetic FF5D success. Other dirty-flag leaf effects are modeled out and unproved. Real storage/display effects are not emulated.'}


def build(data):
    assert len(data) == 0xE0000 and hashlib.sha256(data).hexdigest() == SHA
    thunks = inventory(data)
    assert thunks[0x167C] == (8,0xE7E4)
    gate_checks = 0
    for flags in range(256):
        for entry in (0xFD9D,0xFE7F):
            m = Language(data,thunks);m.x[0xDA68] = flags
            try:m.run(9,entry,budget=80)
            except Boundary:assert m.navigation
            assert m.navigation == (not bool(flags&64))
            assert not m.writes
            gate_checks += 1
    setter_checks = 0
    for old in range(256):
        for proposed in range(256):
            m = Machine(data,thunks);m.x[0xDA03] = old
            m.sr(7,0x32);m.sr(5,proposed)
            m.run(8,0x8B52,budget=300)
            assert m.x[0xDA03] == old
            assert {a for _,_,a in m.writes} == {0xD824}
            assert m.x[0xD824] == 0x32
            setter_checks += 1
    writer_checks = 0
    for old in range(256):
        for staged in range(256):
            m = Language(data,thunks)
            m.x[0xDA03] = old;m.x[0xDA49] = staged;m.x[0xDA69] = 0xA0
            try:m.run(9,0xC6B0,budget=60)
            except Boundary:assert m.post_update
            else:raise AssertionError('Expected post-update boundary')
            assert m.x[0xDA03] == (old&0xC0)|(staged&63)
            assert m.x[0xDA69] == 0xA1 and m.x[0xDA49] == staged
            assert {a for _,_,a in m.writes} == {0xDA03,0xDA69}
            assert {a for _,_,a in m.reads} == {0xDA49,0xDA03,0xDA69}
            writer_checks += 1
    for flags in range(256):
        m = Language(data,thunks)
        m.x[0xDA03] = 0xD4;m.x[0xDA49] = 17;m.x[0xDA69] = flags
        try:m.run(9,0xC6B0,budget=60)
        except Boundary:pass
        assert m.x[0xDA03] == 0xD1 and m.x[0xDA69] == flags|1
    class Proceed(Machine):
        def __init__(self,*args):
            super().__init__(*args);self.changed = False
        def readx(self,address):
            if (self.bank,self.origin) == (9,0xC652):
                self.changed = True
                raise Boundary
            return super().readx(address)
    equality_checks = 0
    for old in range(64):
        for staged in range(64):
            m = Proceed(data,thunks)
            m.x[0xDA03] = old;m.x[0xDA49] = staged
            try:m.run(9,0xC63A,budget=300)
            except Boundary:assert m.changed
            assert m.changed == (old != staged)
            assert {a for _,_,a in m.writes} == {0xD833,0xD834,0xD835}
            equality_checks += 1
    for flags in range(256):
        for carry in (0,1):
            m = Machine(data,thunks);m.x[0xDA69] = flags;m.x[0xDA6C] = 0xA5;m.c = carry
            m.run(8,0xE7E4,budget=100)
            assert m.x[0xDA6C] == (11 if flags else 0xA5)
            assert m.x[0xDA69] == flags
            assert {a for _,_,a in m.writes} == ({0xDA6C} if flags else set())
    return {'firmware_sha256':SHA,'callback_gate_checks':gate_checks,
            'callback_gate':'9:FD9D/FE7F -> C031 only if DA68.bit6 clear; otherwise return. The same flag sends C031 toward navigation at C049, not C0E6 adjustment.',
            'generic_setter_checks':setter_checks,
            'generic_setter':'8:8B52 with selector32 does not update DA03; writes only D824=32. Proposed byte/current packed-language byte exhaustive.',
            'writer_checks':writer_checks,'dirty_flag_checks':256,
            'writer':'9:C6B0..C6C2: DA03=(old&C0)|(DA49&3F); helperA93F sets DA69.bit0; next167C ->8:E7E4 is a stop boundary.',
            'equality_checks':equality_checks,
            'display_event_checks':512,'display_event':'167C ->8:E7E4: if DA69!=0, DA6C=0B; zero leaves DA6C unchanged. DA69 is preserved. Existing DA6C dispatcher sends0B to9:BA6E.',
            'preview_checks':preview_checks(data,thunks),
            'preview':'Normal callback row56: command1 ->9:E7F9 increments staged DA48:DA49 modulo21; command2 ->9:FEEB ->E7F9 decrements modulo21. Uses19D6 ->8:B9A9, upper20/lower0/step1, stops before19DC refresh atE831. DA03 remains unchanged.',
            'apply_root':'Normal row56 command0 ->9:C63A; the checked C6B0 tail commits staged DA49 to DA03 and sets DA69.bit0.',
            'save_event':save_event_checks(data,thunks),
            'entry_comparison':'9:C63A queries current selector32; with DA48=0 and staged DA49=current, returns via C743. Changed low6 values reach C652 before UI effects.',
            'limits':['Every run is offline; no language/monitor/storage change.',
                      'Writer-only checks stop before E7E4; integrated save-event checks execute it and the pending-event save path, excluding preceding apply drawing.',
                      'The equality fixtures use low6 values and DA48=0; entry transition into row56 and further preview/apply drawing effects remain open.',
                      'The writer masks six bits but does not clamp0..20; the separate validator supplies the established stored range.',
                      'Physical button/command labels and complete save/redraw flag lifecycle remain unproved.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('firmware',type=Path);parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args();result = build(args.firmware.read_bytes())
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print('Gate/setter/writer/equality checks:',result['callback_gate_checks'],result['generic_setter_checks'],result['writer_checks'],result['equality_checks'])


if __name__ == '__main__':main()

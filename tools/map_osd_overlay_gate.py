"""Verify DA72 refresh suppression, overlay producers and deferred SET release."""
import argparse
import hashlib
import json
from pathlib import Path
from analyze_banked_abi import SHA, inventory, traverse, word
from emulate_mcs51 import Machine
from map_osd_language_layout import Window
from map_osd_notifications import LANGUAGE_CODES
from map_osd_storage import StorageMachine, expected_pages


def initial(data,thunks):
    m = Window(data,thunks);m.x[0xFFFF] = 13;m.ram[0x39] = 1
    m.x[0xDAD3:0xDAD7] = (60000000).to_bytes(4,'big')
    return m


def build(data):
    assert len(data) == 0xE0000 and hashlib.sha256(data).hexdigest() == SHA
    thunks = inventory(data);leaf_checks = 0
    for old in range(256):
        for entry,expected in ((0xB7CE,old|8),(0xFC1B,old&0xE7)):
            m = Machine(data,thunks);m.x[0xDA72] = old
            m.run(9,entry,budget=20)
            assert m.x[0xDA72] == expected
            assert {a for _,_,a in m.writes} == {0xDA72}
            leaf_checks += 1
    decoded,_,_,reserved,overlaps = traverse(data,thunks)
    assert not reserved and not overlaps
    callers = []
    for bank,pc in sorted(decoded):
        p = bank*65536+pc
        if data[p] in (2,18):
            target = word(data,p+1)
            if thunks.get(target,(bank,target)) == (9,0xB7CE):
                callers.append(f'{bank}:{pc:04X}')
    assert callers == ['9:BD38','9:C882','9:EC93']
    producers = []
    for entry in (0xBD2F,0xC84C,0xEC90):
        for gate in (0,8,16,24):
            for state in (0,0x56):
                for dirty in (0,1):
                    m = initial(data,thunks);m.x[0xDA03] = 1
                    m.x[0xDA72] = gate;m.x[0xDA6B] = state;m.x[0xDA69] = dirty
                    m.run(9,entry,budget=2000000)
                    assert m.x[0xDA72]&8 and m.x[0xDA69] == dirty
                    assert m.x[0xDA03] == 1 and not m.stack and not m.calls
                    assert not ({a for _,_,a in m.writes}&set(range(0xFF55,0xFF5F)))
                    producers.append({'entry':f'9:{entry:04X}','initial_DA72':gate,
                                      'initial_DA6B':state,'initial_dirty':dirty,
                                      'final_DA72':m.x[0xDA72],'final_DA6B':m.x[0xDA6B],
                                      'final_DA6C':m.x[0xDA6C],'window_frames':len(m.frames),
                                      'steps':m.steps})
    release_checks = save_checks = 0
    for language,code in enumerate(LANGUAGE_CODES):
        for high in (0,64,128,192):
            for gate in (8,24):
                m = initial(data,thunks);m.x[0xDA03] = high|((language+1)%21)
                m.x[0xDA6B] = 0x56;m.x[0xDA72] = gate;m.x[0xD9FD] = 1
                m.x[0xD993] = 0xCC;m.x[0xD995] = code
                m.run(9,0x9452,budget=100000)
                assert (m.x[0xDA03],m.x[0xDA69],m.x[0xDA6C]) == (high|language,1,0)
                m.run(9,0xFC11,budget=100000)
                assert (m.x[0xDA03],m.x[0xDA69],m.x[0xDA6C],m.x[0xDA6B],m.x[0xDA72]) == (high|language,1,11,0,0)
                assert not m.calls and not m.stack
                release_checks += 1
                for flags in (0,8):
                    for profile in range(4):
                        s = StorageMachine(data,thunks);s.ram[:] = m.ram;s.x[:] = m.x
                        s.x[0xDA87] = flags;s.x[0xD9FE] = profile<<2
                        s.run(9,0xB8B2,budget=30000)
                        assert (s.x[0xDA69],s.x[0xDA6C],s.x[0xDA03]) == (0,0,high|language)
                        offset = 0x32+36*profile if flags&8 else 0x0E
                        assert [(f['address'],f['count'],f['slave']) for f in s.frames] == expected_pages(offset,36)
                        payload = b''.join(f['payload'] for f in s.frames)
                        assert payload == bytes(s.x[0xD9FD:0xDA21]) and payload[6] == high|language
                        save_checks += 1
    return {'firmware_sha256':SHA,'leaf_checks':leaf_checks,
            'direct_setter_callers_in_default_CFG':callers,'producer_checks':len(producers),
            'producer_fixtures':producers,'deferred_release_checks':release_checks,
            'release_save_checks':save_checks,
            'bit_setter':'9:B7CE setsDA72.bit3, preserving every other bit.',
            'clear_leaf':'9:FC1B clearsDA72.bits3/4, preserving every other bit.',
            'release':'9:FC11 executes15F8/10:F439, then15FE/1:FA88 withR7=0/R5=1, thenFC1B clearsbits3/4. Pending dirty language is published asDA6C0B during F439 before flags clear.',
            'interpretation':'DA72.bit3 suppresses normal SET refresh while these drawing/overlay-producing paths own the OSD. Overlay gate is strong evidence; exact physical screen names are not assigned.',
            'limits':['Offline only; Window supplies synthetic burst busy-bit completion; StorageMachine supplies synthetic FF5D success.',
                      'Direct caller inventory is limited to checked default static CFG and direct LCALL/LJMP instructions, not exhaustive indirect/address-propagated writers.',
                      'Producer fixtures cover only explicit initial gate/state/dirty combinations; no interrupts or live visibility.',
                      'CallingFC11 proves a release/save route exists; it does not prove every runtime deferred SET necessarily reaches that route.',
                      'The bit3 clear inside9:A203..A20C is a separate conditional branch not executed here.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('firmware',type=Path);parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args();result = build(args.firmware.read_bytes())
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print('Gate leaf/producer/release/save checks:',*(result[k] for k in
          ('leaf_checks','producer_checks','deferred_release_checks','release_save_checks')))


if __name__ == '__main__':main()

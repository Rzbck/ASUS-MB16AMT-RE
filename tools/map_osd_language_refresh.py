"""Execute complete language SET/refresh and pending-save paths offline."""
import argparse
import hashlib
import json
from pathlib import Path
from analyze_banked_abi import SHA, inventory
from map_osd_language_layout import Window
from map_osd_notifications import LANGUAGE_CODES
from map_osd_storage import StorageMachine, expected_pages


def build(data):
    assert len(data) == 0xE0000 and hashlib.sha256(data).hexdigest() == SHA
    thunks = inventory(data);complete = saved = deferred = steps = 0
    write_addresses = set();refresh_steps = set()
    for language,code in enumerate(LANGUAGE_CODES):
        for high in (0,64,128,192):
            for gate in (0,8):
                for flags in (0,8):
                    for profile in range(4):
                        m = Window(data,thunks);m.x[0xFFFF] = 13;m.ram[0x39] = 1
                        m.x[0xDAD3:0xDAD7] = (60000000).to_bytes(4,'big')
                        m.x[0xD9FD] = 1;m.x[0xD9FE] = profile<<2
                        m.x[0xDA03] = high|((language+1)%21)
                        m.x[0xDA6B] = 0x56;m.x[0xDA72] = gate;m.x[0xDA87] = flags
                        m.x[0xDCC4] = 0xA5;m.sbit(0x25,1)
                        m.x[0xD993:0xD996] = bytes((0xCC,0xA5,code))
                        m.run(9,0x9452,budget=100000)
                        assert m.x[0xDA03] == high|language and m.x[0xDA69] == 1
                        assert (m.x[0xDA6B],m.x[0xDA6C]) == ((0x56,0) if gate else (0,11))
                        assert (m.x[0xDCC4],m.x[0xDCC5],m.bit(0x25)) == (0xA5,0xCC,0)
                        assert m.x[0xDA72] == gate and m.x[0xDA87] == flags
                        assert not m.stack and not m.calls
                        assert not ({a for _,_,a in m.writes}&set(range(0xFF55,0xFF5F)))
                        assert not m.frames
                        writes = {a for _,_,a in m.writes};write_addresses.update(writes)
                        assert ((13,0x6803) in m.visited) == (not bool(gate))
                        if gate:
                            # Event dispatcher has no pending0B: preserve dirty language.
                            m.run(9,0xB8B2,budget=500)
                            assert m.x[0xDA69] == 1 and m.x[0xDA6C] == 0
                            deferred += 1
                        else:
                            refresh_steps.add(m.steps)
                            # Carry exact RAM/XDATA into existing storage model after top RET.
                            s = StorageMachine(data,thunks)
                            s.ram[:] = m.ram;s.x[:] = m.x
                            s.run(9,0xB8B2,budget=30000)
                            assert (s.x[0xDA69],s.x[0xDA6C],s.x[0xDA03]) == (0,0,high|language)
                            offset = 0x32+36*profile if flags&8 else 0x0E
                            assert [(f['address'],f['count'],f['slave']) for f in s.frames] == expected_pages(offset,36)
                            payload = b''.join(f['payload'] for f in s.frames)
                            assert payload == bytes(s.x[0xD9FD:0xDA21]) and payload[6] == high|language
                            assert s.pin == [v for _ in s.frames for v in (0,1)]
                            assert not s.calls and not s.stack
                            saved += 1
                        complete += 1;steps += m.steps
    unsupported = []
    for code in (0,0xFF):
        m = Window(data,thunks);m.x[0xFFFF] = 13;m.ram[0x39] = 1
        m.x[0xDAD3:0xDAD7] = (60000000).to_bytes(4,'big')
        m.x[0xDA03] = 0xC7;m.x[0xDA6B] = 0x56;m.x[0xD993] = 0xCC;m.x[0xD995] = code
        m.run(9,0x9452,budget=100000)
        assert (m.x[0xDA03],m.x[0xDA69],m.x[0xDA6C],m.x[0xDA6B]) == (0xC7,1,11,0)
        unsupported.append(f'{code:02X}')
    return {'firmware_sha256':SHA,'complete_set_checks':complete,
            'integrated_save_checks':saved,'deferred_dispatch_checks':deferred,
            'unsupported_complete_checks':unsupported,'complete_set_and_deferred_dispatch_steps':steps,
            'refresh_set_step_counts':sorted(refresh_steps),
            'set_refresh_write_addresses':[f'{a:04X}' for a in sorted(write_addresses)],
            'chain':'9:9452 ->9883 language ->997A/9C99 dirty ->9CA2 DA72.bit3 ->15F8/10:F439 ->167C/8:E7E4 event0B ->top RET; pending9:B8B2/BA6E ->15C2/8:DDB3 ->01D0 storage writer.',
            'clear_gate':'Complete original F439 and all selector callees execute; DA6B becomes0 and DA6C becomes0B. No window burst frames are prepared in these fixtures; register/OSD port writes do occur.',
            'set_gate':'F439 is bypassed; DA6B remains56, DA6C remains0. A subsequent event dispatcher call leaves DA69.bit0 pending and emits no language save event.',
            'save':'Existing StorageMachine supplies synthetic FF5D completion; page payload byte6 is applied packedDA03 in every clear-gate fixture.',
            'coverage':'21 languages x4 DA03 high2 x2 DA72.bit3 x2 DA87.bit3 x4 profile fixtures; all other state startszero except explicit bank13/RAM39=1/nonzeroDAD3/D9FD=1.',
            'limits':['Entirely offline; no host/monitor command.',
                      'FFF3 busy bits are synthetic clear via existing Window model; real display visibility and register effects are not verified.',
                      'Only the checked initial states are whole-path coverage, not all F439 branches.',
                      'No interrupts run; later producers may publish another event for deferred dirty language.',
                      'Physical storage completion is not proved by synthetic FF5D.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('firmware',type=Path);parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args();result = build(args.firmware.read_bytes())
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print('Complete SET/save/deferred:',*(result[k] for k in
          ('complete_set_checks','integrated_save_checks','deferred_dispatch_checks')))


if __name__ == '__main__':main()

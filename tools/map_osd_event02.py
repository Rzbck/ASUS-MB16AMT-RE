"""Execute event02 under explicit early-wait-exit and bounded polling fixtures."""
import argparse
import hashlib
import json
from pathlib import Path
from analyze_banked_abi import SHA, inventory
from emulate_mcs51 import Machine
from map_osd_language_layout import Window


class Event(Window):
    def __init__(self,*args):
        super().__init__(*args);self.requests = [];self.event_writes = []
    def jump(self,target,call=False):
        if target in (0x0B72,0x0B7E):
            self.requests.append({'site':f'{self.bank}:{self.origin:04X}',
                                  'primitive':f'{target:04X}','argument':self.r(6)*256+self.r(7),
                                  'event':f'{self.r(5):02X}'})
        super().jump(target,call)
    def writex(self,address,value):
        if address == 0xDA6C:self.event_writes.append((self.bank,self.origin,value&255))
        super().writex(address,value)


def build(data):
    assert len(data) == 0xE0000 and hashlib.sha256(data).hexdigest() == SHA
    thunks = inventory(data);delay_checks = 0
    for duration in range(65536):
        m = Machine(data,thunks);m.sr(6,duration>>8);m.sr(7,duration&255);m.x[0x9C70] = 4
        m.run(2,0xFA66,budget=100)
        assert int.from_bytes(m.x[0xD825:0xD827],'big') == duration and m.r(7) == 0
        assert m.bit(3) == 1 and m.ram[0x42:0x44] == bytes(2)
        assert {a for _,_,a in m.writes} == {0xD825,0xD826};delay_checks += 1
    fixtures = [(state,gate,dirty,1) for state in (0,0x32,0x56,0x58)
                for gate in (0,8) for dirty in (0,1)]
    fixtures += [(0,0,0,language) for language in range(21)]
    results = [];write_addresses = set()
    for state,gate,dirty,language in fixtures:
        m = Event(data,thunks);m.x[0xFFFF] = 13;m.ram[0x36] = m.ram[0x39] = 1
        m.x[0xDAD3:0xDAD7] = (60000000).to_bytes(4,'big');m.x[0x9C70] = 4
        m.x[0xDA03] = language;m.x[0xDA6B] = state;m.x[0xDA72] = gate
        m.x[0xDA69] = dirty;m.x[0xDA6C] = 2
        m.run(9,0xB8B2,budget=1000000)
        assert (m.x[0xDA03],m.x[0xDA6B],m.x[0xDA69],m.x[0xDA6C]) == (language,0,dirty,0)
        assert m.x[0xDA72] == 0
        assert not m.calls and not m.stack
        assert m.event_writes[-1] == (9,0xBAE5,0)
        assert int.from_bytes(m.x[0xD92E:0xD930],'big') == 60000 and m.x[0xD92D] == 0x11
        assert bytes(m.x[0xD930:0xD933]) == bytes.fromhex('08 0B B8')
        assert [(r['site'],r['event'],r['argument']) for r in m.requests] == [('6:99E0','11',60000),('9:BADE','08',3000)]
        assert m.event_writes == ([(8,0xE829,11),(9,0xBAE5,0)] if dirty else [(9,0xBAE5,0)])
        write_addresses.update(a for _,_,a in m.writes if a<0xD000)
        results.append({'initial_DA6B':f'{state:02X}','initial_DA72':f'{gate:02X}',
                        'initial_dirty':dirty,'language':language,'steps':m.steps,
                        'final_DA72':f'{m.x[0xDA72]:02X}','window_frames':len(m.frames),
                        'timer_requests':m.requests,
                        'event_writes':[f'{b}:{pc:04X}={v:02X}' for b,pc,v in m.event_writes]})
    return {'firmware_sha256':SHA,'early_wait_exit_checks':delay_checks,
            'complete_event02_checks':len(results),'fixtures':results,
            'register_write_addresses_union':[f'{a:04X}' for a in sorted(write_addresses)],
            'chain':'9:B8B2 ->B935 ->1622/10:D760(R7=1) ->BAF3 ->BAE7(A=0) ->0C4A/6:98B9(R7=2) ->DA6F low-nibbleclear ->BADE timer08 argument3000 ->BAE1 eventclear.',
            'wait_exit':'2:FA66..FAAE storesR6:R7 inD825:D826. With9C70.bit2 set, bit03 staysset and the loop returns without RAM42:43 advancing; verified all65536 arguments.',
            'complete_effects':'Checked37 fixtures returnDA6B0/DA6C0, retainlanguage/dirtybit0; actual original timer slots contain11:EA60 then08:0BB8 underzero timing snapshot.',
            'limits':['Offline bytearray execution only; nohardwarecommand.',
                      'Window syntheticburstcompletion,bank13,RAM36/RAM39=1,DAD3=60000000,9C70.bit2=1 are explicit fixtures, not measured hardwarestate.',
                      '9DB1 stayszero in polling portions: bounded retries/error branches execute. Whole handler completion is not successful physical I2C/display proof.',
                      '9C70.bit2 clear withstaticRAM42:43 doesnotprogress atwait; realclockproducer/interrupttiming remainsopen.',
                      'ANL C,bit82 nowexecuted byinterpreter and independently checked bycheck_mcs51_bit_logic.py.',
                      'No semanticname assignedtoevent02 screen/status or timer11.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('firmware',type=Path);parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args();result = build(args.firmware.read_bytes())
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print('Event02 wait/complete checks:',result['early_wait_exit_checks'],result['complete_event02_checks'])


if __name__ == '__main__':main()

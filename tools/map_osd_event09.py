"""Execute event09 reset/status/clear path offline; no hardware command."""
import argparse
import hashlib
import json
from pathlib import Path
from analyze_banked_abi import SHA, inventory
from emulate_mcs51 import Machine
from map_osd_language_layout import Window


class Event(Window):
    def __init__(self,*args):
        super().__init__(*args);self.event_writes = []
    def writex(self,address,value):
        if address == 0xDA6C:self.event_writes.append((self.bank,self.origin,value&255))
        super().writex(address,value)


def build(data):
    assert len(data) == 0xE0000 and hashlib.sha256(data).hexdigest() == SHA
    thunks = inventory(data);status_checks = complete = steps = 0
    for packed in range(256):
        for secondary in range(256):
            for value in (2,3):
                m = Machine(data,thunks);m.sr(7,value)
                m.x[0xDCC9] = packed;m.x[0xDCCA] = secondary
                m.run(7,0xF82D,budget=60)
                assert m.x[0xDCC9] == (packed&0xF0)|value
                assert m.x[0xDCCA] == (secondary&0xBF if value == 2 else secondary)
                assert {a for _,_,a in m.writes} == ({0xDCC9,0xDCCA} if value == 2 and secondary&64 else {0xDCC9})
                status_checks += 1
    event_sequences = {}
    for state in (0,0x32,0x56,0x58):
        for gate in (0,8,16,24):
            for packed in (0,0x23,0x80,0xFF):
                for secondary in (0,64):
                    for dirty in (0,1):
                        m = Event(data,thunks);m.x[0xFFFF] = 13;m.ram[0x39] = 1
                        m.x[0xDAD3:0xDAD7] = (60000000).to_bytes(4,'big')
                        m.x[0xDA03] = 0xC7;m.x[0xDA6B] = state;m.x[0xDA72] = gate
                        m.x[0xDA69] = dirty;m.x[0xDA6C] = 9
                        m.x[0xDCC9] = packed;m.x[0xDCCA] = secondary
                        m.run(9,0xB8B2,budget=100000)
                        assert (m.x[0xDA03],m.x[0xDA6B],m.x[0xDA72],m.x[0xDA69],m.x[0xDA6C]) == (0xC7,0,gate,dirty,0)
                        assert (m.x[0xDCC9],m.x[0xDCCA]) == ((packed&0xF0)|3,secondary)
                        expected = [(8,0xE829,11),(9,0xBAE5,0)] if dirty else [(9,0xBAE5,0)]
                        assert m.event_writes == expected, m.event_writes
                        assert not m.stack and not m.calls and not m.frames
                        assert not ({a for _,_,a in m.writes}&set(range(0xFF55,0xFF5F)))
                        event_sequences[str(dirty)] = [f'{b}:{pc:04X}={value:02X}' for b,pc,value in m.event_writes]
                        complete += 1;steps += m.steps
    return {'firmware_sha256':SHA,'status_writer_checks':status_checks,
            'complete_event09_checks':complete,'steps':steps,'event_write_sequences_by_initial_dirty':event_sequences,
            'chain':'9:B8B2 ->BA15 ->15F8/10:F439 ->R7=3 ->BACE/18C8/7:F82D ->BAE1 eventclear ->RET.',
            'status_writer':'7:F82D replacesDCC9 low nibble withR7&0F, preserveshigh; onlyR7=2 clearsDCCA.bit6 whenitwas set. Event09 supplies3 and retainsDCCA.',
            'complete_effects':'UndercheckedfixturesDA6B=0,DA03/DA72/DA69retained,DCC9low=3,DA6C=0; noI2Cstoragewrites.',
            'nested_event':'Initialdirtybit0 causesF439/E7E4 towriteDA6C0B, thenouterBAE1 overwritesitwith0. Dirtybit0 remains; this handlerdoesnotsaveit.',
            'coverage':'4 menustates x4 DA72flags x4 DCC9bytes x2 DCCA.bit6 x2 dirtyflags; otherstatezeroexceptbank13/RAM39=1/DAD3nonzero.',
            'limits':['Offline only; existing Window supplies synthetic burstbusy completion.',
                      'Nested eventoverwrite is localproof, not globalpermanentloss; laterproducers/interrupts couldpublishanother0B.',
                      'No physicalstatus nameisassignedtoDCC9low3.',
                      'Event02 wholeexecution remainsopenat2:FA77..FAAE RAMclock-dependentwait; zero-clock snapshotdoesnotprogress.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('firmware',type=Path);parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args();result = build(args.firmware.read_bytes())
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print('Event09 status/complete checks:',result['status_writer_checks'],result['complete_event09_checks'])


if __name__ == '__main__':main()

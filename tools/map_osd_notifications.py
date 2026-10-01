"""Verify OSD change notifications and language GET replies without transport."""
import argparse
import hashlib
import json
from pathlib import Path
from analyze_banked_abi import SHA, inventory
from emulate_mcs51 import Machine
from trace_battery_provenance import GetVcp, ReplyDone


LANGUAGE_CODES = (2,3,4,10,5,20,9,30,18,17,26,31,8,12,13,1,6,7,48,35,49)


def reply(data,thunks,opcode,status=2,last=0xCC,consumed=0,language=0):
    m = GetVcp(data,thunks);m.x[0xD993] = opcode
    m.x[0xDCC4] = status;m.x[0xDCC5] = last;m.sbit(0x25,consumed)
    m.x[0xDA03] = language
    try:m.run(9,0xA3A0,budget=1000)
    except ReplyDone:pass
    else:raise AssertionError('Expected existing pre-transport boundary')
    packet = bytes(m.x[0xD9C0:0xD9CB])
    assert packet[:6] == bytes((0x6E,0x88,2,0,opcode,0))
    checksum = 0x50
    for value in packet:checksum ^= value
    assert checksum == 0
    assert {a for _,_,a in m.writes} <= set(range(0xD820,0xD828))|set(range(0xD9C0,0xD9CB))|{0xDCC4}
    assert not ({a for _,_,a in m.writes}&{0xDA03,0xDA69,0xDA6C})
    return m,int.from_bytes(packet[6:8],'big'),int.from_bytes(packet[8:10],'big')


def build(data):
    assert len(data) == 0xE0000 and hashlib.sha256(data).hexdigest() == SHA
    thunks = inventory(data);chunk = data[9*65536:10*65536]
    cases = {};pos = 0xA3D1
    while int.from_bytes(chunk[pos:pos+2],'big'):
        assert pos < 0xA462
        assert chunk[pos+2] not in cases
        cases[chunk[pos+2]] = int.from_bytes(chunk[pos:pos+2],'big');pos += 3
    assert {op:cases[op] for op in (2,0x52,0xCC)} == {2:0xA462,0x52:0xA5B7,0xCC:0xA726}
    assert tuple(chunk[0x9426:0x943B]) == LANGUAGE_CODES
    marker_checks = 0
    for code in range(256):
        for bits in range(256):
            m = Machine(data,thunks);m.sr(7,code);m.ram[0x24] = bits
            m.x[0xDCC4:0xDCC6] = bytes((0xA5,0x5A))
            m.run(9,0xFD52,budget=30)
            assert bytes(m.x[0xDCC4:0xDCC6]) == bytes((2,code))
            assert m.ram[0x24] == bits&0xDF
            assert {a for _,_,a in m.writes} == {0xDCC4,0xDCC5}
            marker_checks += 1
    status_checks = 0
    for status in range(256):
        for consumed in (0,1):
            m,maximum,current = reply(data,thunks,2,status=status,consumed=consumed)
            assert (maximum,current) == (2,status)
            assert (m.x[0xDCC4],m.x[0xDCC5],m.bit(0x25)) == (status,0xCC,consumed)
            status_checks += 1
    active_checks = 0
    for status in (0,1,2,255):
        for code in range(256):
            for consumed in (0,1):
                m,maximum,current = reply(data,thunks,0x52,status=status,last=code,consumed=consumed)
                assert (maximum,current) == (255,0 if consumed else code)
                assert (m.x[0xDCC4],m.x[0xDCC5],m.bit(0x25)) == (1,code,1)
                reads = {a for _,_,a in m.reads}
                assert (0xDCC5 in reads) == (not consumed)
                active_checks += 1
    language_checks = 0
    for index,code in enumerate(LANGUAGE_CODES):
        for high in (0,64,128,192):
            for consumed in (0,1):
                m,maximum,current = reply(data,thunks,0xCC,language=high|index,consumed=consumed)
                assert (maximum,current) == (0x31,code)
                assert (m.x[0xDCC4],m.x[0xDCC5],m.bit(0x25)) == (2,0xCC,consumed)
                language_checks += 1
    # Compose the exact marker and consumer instructions on one machine.
    m = GetVcp(data,thunks);m.sr(7,0xCC);m.sbit(0x25,1)
    m.run(9,0xFD52,budget=30)
    currents = []
    for opcode in (2,0x52,2,0x52):
        m.x[0xD993] = opcode
        try:m.run(9,0xA3A0,budget=1000)
        except ReplyDone:pass
        else:raise AssertionError('Expected pre-transport boundary')
        currents.append(int.from_bytes(m.x[0xD9C8:0xD9CA],'big'))
    assert currents == [2,0xCC,1,0]
    return {'firmware_sha256':SHA,'marker_checks':marker_checks,
            'status_get_checks':status_checks,'active_get_checks':active_checks,
            'language_get_checks':language_checks,'sequence_checks':1,
            'get_targets':{f'{op:02X}':f'9:{cases[op]:04X}' for op in (2,0x52,0xCC)},
            'marker':'9:FD52 setsDCC4=2/DCC5=R7 and clears directbit25, preserving all other RAM24 bits.',
            'status':'GET02 replies type0/max2/currentDCC4; leaves record and bit25 unchanged.',
            'active':'GET52: bit25clear ->reply type0/maxFF/currentDCC5, then setbit25; already-set ->current0 without readingDCC5. Both paths setDCC4=1 and retainDCC5.',
            'sequence':'FD52 R7CC ->GET02 current2 ->GET52 currentCC ->GET02 current1 ->GET52 current0.',
            'language':'GETCC readsDA03&3F and MOVC code9:9426+index; type0/max31/currenttranslatedcode. Record/bit25 unchanged. Checked valid indices0..20 with all high-bit combinations.',
            'language_protocol_codes':[{'internal_index':i,'GET_CC_current':f'{code:02X}'} for i,code in enumerate(LANGUAGE_CODES)],
            'reply_validation':'Original9:A3A0 dispatcher,13:6699 payload builder and187A checksum execute; existing GetVcp stops before9:1298 transport. Every tested frame XORs to50 including checksum.',
            'limits':['No host/monitor/DDC command is sent; all execution is offline.',
                      'GET52 mutates the modeled notification state; do not classify it as side-effect-free merely because it is a protocol GET.',
                      'Protocol identifiers match pinned reference names, but native-script language names require separate glyph/source evidence.',
                      'GETCC does not clamp low6 indices itself; invalid21..63 behavior is outside this valid-language contract.',
                      'This establishes OSD-to-host change reporting, not a receive-side SET handler or a live charging/SOC primitive.']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('firmware',type=Path);p.add_argument('--out',type=Path,required=True)
    args = p.parse_args();result = build(args.firmware.read_bytes())
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print('Marker/status/active/language GET checks:',*(result[k] for k in
          ('marker_checks','status_get_checks','active_get_checks','language_get_checks')))


if __name__ == '__main__':main()

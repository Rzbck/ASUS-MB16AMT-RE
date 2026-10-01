"""Verify OSD storage page planning and I2CM register frames entirely offline."""
import argparse
import hashlib
import json
from pathlib import Path

from analyze_banked_abi import SHA, inventory
from emulate_mcs51 import Machine


class StorageMachine(Machine):
    def __init__(self, *args, boundary=False, failure=None):
        super().__init__(*args)
        self.boundary = boundary
        self.failure = failure
        self.frames = []
        self.polls = []
        self.fifo = []
        self.control = []
        self.pin = []
        self.status_reads = 0
        self.ram[0x39] = 1  # Actual firmware busy-loop executes, without timing.

    def jump(self, target, call=False):
        if target == 0x0707 and self.origin == 0x04C3:
            self.frames.append({
                'slave': self.r(7), 'mode': self.r(5),
                'address': (self.r(2) << 8) | self.r(3),
                'count': self.x[0xD8A3], 'interface': self.x[0xD8A7],
                'pointer': bytes(self.x[0xD8A4:0xD8A7]),
                'payload': bytes(self.x[0xD842:0xD842+self.x[0xD8A3]]),
                'fifo_start': len(self.fifo)})
            if self.boundary:
                self.c = 1
                return
        if target == 0x14CC and self.origin == 0x053A:
            self.polls.append((self.r(7), self.r(5), self.r(3)))
            self.frames[-1]['fifo_end'] = len(self.fifo)
            if self.boundary:
                self.c = 1
                return
        super().jump(target, call)

    def readx(self, address):
        if address == 0xFF5D:
            self.status_reads += 1
            # Explicit synthetic peripheral status; no bus is emulated.
            self.x[address] = 0x21
            if self.failure == 'initial' and self.bank == 8:
                self.x[address] = 0
            elif self.failure == 'completion' and self.bank == 8:
                self.x[address] = 0x20
            elif self.failure == 'poll' and self.bank == 0:
                self.x[address] = 0
        return super().readx(address)

    def writex(self, address, value):
        if address == 0xFF5E:self.fifo.append(value & 255)
        if address == 0xFF55:self.control.append(value & 255)
        if address == 0xFE08:self.pin.append(value & 255)
        super().writex(address, value)


def expected_pages(address, length):
    result = []
    while length:
        count = min(length, 16-(address & 15))
        result.append((address, count, (0xA0+2*((address >> 8) & 255)) & 255))
        address += count
        length -= count
    return result


def init_writer(machine, address, length):
    payload = bytes((i*37+11) & 255 for i in range(length))
    machine.x[0x9000:0x9000+length] = payload
    machine.sr(3, 1);machine.sr(2, 0x90);machine.sr(1, 0)
    machine.sr(6, address >> 8);machine.sr(7, address & 255)
    machine.sr(4, length >> 8);machine.sr(5, length & 255)
    return payload


def assert_pages(machine, address, length, payload):
    expected = expected_pages(address, length)
    assert [(f['address'],f['count'],f['slave']) for f in machine.frames] == expected
    assert machine.c == bool(length)  # Zero-length entry returns carry clear.
    assert machine.polls == [(slave, 1, 11) for _,_,slave in expected]
    consumed = 0
    for frame in machine.frames:
        assert frame['mode'] == 1 and frame['interface'] == 11
        assert frame['pointer'] == bytes((1, 0xD8, 0x42))
        assert frame['payload'] == payload[consumed:consumed+frame['count']]
        consumed += frame['count']
    assert machine.pin == [v for _ in expected for v in (0, 1)]
    assert int.from_bytes(machine.x[0xD830:0xD834], 'big') == address+length
    assert int.from_bytes(machine.x[0xD835:0xD839], 'big') == 0
    assert bytes(machine.x[0xD839:0xD83C]) == bytes((1, (0x9000+length) >> 8, length & 255))
    assert bytes(machine.x[0x9000:0x9000+length]) == payload


def page_checks(data, thunks):
    checks = 0
    # All low address bytes, short/zero lengths and multi-page settings length.
    starts = list(range(256)) + [0x100+i for i in (0,14,15,254,255)]
    starts += [0x200+i for i in (0,14,15,254,255)]
    starts += [0x7F00+i for i in (0,14,15,254,255)]
    starts += [0xFE00+i for i in (0,14,15,254,255)]
    for address in starts:
        for length in (0,1,15,16,17,36):
            m = StorageMachine(data, thunks, boundary=True)
            payload = init_writer(m, address, length)
            m.run(8, 0x01D0, budget=20000)
            assert_pages(m, address, length, payload)
            assert not m.fifo
            assert {a for _,_,a in m.writes} <= set(range(0xD82B,0xD852)) | set(range(0xD8A3,0xD8A8)) | {0xFE08}
            checks += 1
    return checks


def frame_checks(data, thunks):
    checks = 0
    for address in range(256):
        for count in range(1,17):
            m = StorageMachine(data, thunks)
            payload = bytes((address+i*37) & 255 for i in range(count))
            m.x[0x9000:0x9000+count] = payload
            m.x[0xD8A3:0xD8A8] = bytes((count,1,0x90,0,11))
            m.x[0xFF55] = address;m.x[0xFF57] = address;m.x[0xFF58] = address
            m.sr(7,0xA0);m.sr(5,1);m.sr(2,0);m.sr(3,address)
            m.run(8,0x0707,budget=3000)
            assert m.c == 1
            assert m.fifo == [0xA0,address]+list(payload)
            assert m.control == [address & 0xC1,0xC0+2*count]
            assert m.x[0xFF55] == 0xC0+2*count
            assert m.x[0xFF57] == address & 0xFC
            assert m.x[0xFF58] == address & 0xE7
            assert m.x[0xFF5D] == 0x27
            assert bytes(m.x[0x9000:0x9000+count]) == payload
            assert m.status_reads == 3  # Ready, completion and status-ack read.
            assert m.x[0x1019] == 0x80 and bytes(m.x[0x1032:0x1034]) == bytes((0,0))
            checks += 1
    return checks


def full_writer_checks(data, thunks):
    slots = []
    for address in (0x0E,0x32,0x56,0x7A,0x9E):
        m = StorageMachine(data, thunks)
        payload = init_writer(m, address,36)
        m.run(8,0x01D0,budget=20000)
        assert_pages(m,address,36,payload)
        for frame in m.frames:
            fifo = m.fifo[frame['fifo_start']:frame['fifo_end']]
            assert fifo == [frame['slave'],frame['address'] & 255]+list(frame['payload'])
        # Poll mode1 sends the same slave and a zero byte, set by 0:5705.
        expected_fifo = []
        for frame in m.frames:
            expected_fifo += [frame['slave'],frame['address'] & 255]+list(frame['payload'])
            expected_fifo += [frame['slave'],0]
        assert m.fifo == expected_fifo
        slots.append({'offset':f'{address:04X}', 'pages':[
            {'offset':f'{p:04X}','length':n,'slave':f'{s:02X}'} for p,n,s in expected_pages(address,36)]})
    failures = []
    for failure, reads, fifo_count, polls in (
            ('initial',601,0,0), ('completion',602,4,0), ('poll',12003,104,50)):
        m = StorageMachine(data, thunks, failure=failure)
        init_writer(m,0x0E,36)
        m.run(8,0x01D0,budget=500000)
        assert m.c == 0 and m.pin == [0,1]
        assert len(m.frames) == 1 and len(m.polls) == polls
        assert len(m.fifo) == fifo_count and m.status_reads == reads
        assert m.x[0xD841] == (0 if polls else 50)
        # Source/remaining length advanced before attempting the first frame.
        assert int.from_bytes(m.x[0xD835:0xD839],'big') == 34
        assert bytes(m.x[0xD839:0xD83C]) == bytes((1,0x90,2))
        assert int.from_bytes(m.x[0xD830:0xD834],'big') == (0x10 if polls else 0x0E)
        failures.append({'status_fixture':failure,'carry':0,'FF5D_reads':reads,'poll_calls':polls})
    return slots, failures


def mux_checks(data,thunks):
    for selector in range(256):
        m = Machine(data,thunks,fill=0x5A);m.sr(7,selector)
        m.run(8,0xEAFE,budget=50)
        expected = {10:{0x1019:0,0x101A:0,0x1032:0,0x1033:0},
                    11:{0x1019:128,0x1032:0,0x1033:0},
                    12:{0x1032:128,0x1019:0,0x101A:0}}.get(selector,{})
        assert {a for _,_,a in m.writes} == set(expected)
        for address,value in expected.items():assert m.x[address] == value
    return 256


def validated_save_checks(data, thunks):
    class Validated(StorageMachine):
        def jump(self,target,call=False):
            if (self.bank,self.origin,target) == (8,0xDE1A,0x01D0):
                self.validated = bytes(self.x[0xD9FD:0xDA21])
            super().jump(target,call)
    checks = 0
    for flags in (0,8):
        for profile in range(4):
            for lock in (0,64):
                m = Validated(data,thunks)
                m.x[0xDA87] = flags;m.x[0xD9FE] = profile << 2
                m.x[0xD9FD] = 1 | lock
                m.run(8,0xDDB3,budget=20000)
                offset = 0x32+0x24*profile if flags&8 else 0x0E
                assert [(f['address'],f['count'],f['slave']) for f in m.frames] == expected_pages(offset,36)
                assert b''.join(f['payload'] for f in m.frames) == m.validated
                assert bytes(m.x[0xD9FD:0xDA21]) == m.validated
                assert m.c == 1 and m.validated[0] & 64 == lock
                checks += 1
    return checks


def build(data):
    assert len(data) == 0xE0000 and hashlib.sha256(data).hexdigest() == SHA
    thunks = inventory(data)
    pages = page_checks(data,thunks)
    frames = frame_checks(data,thunks)
    slots,failures = full_writer_checks(data,thunks)
    mux = mux_checks(data,thunks)
    validated = validated_save_checks(data,thunks)
    return {'firmware_sha256':SHA,
            'entry':'common 01D0, executed in bank 8',
            'abi':{'source':'R3:R2:R1 generic pointer','length':'R4:R5 BE16','offset':'R6:R7 BE16','return':'Carry=1 after all nonempty chunks complete; zero length returns 0; transfer/poll timeout returns 0.'},
            'configuration':{'slave_base':'A0 (eight-bit bus byte)','address_mode':1,'interface':'0B','page_size':16},
            'page_rule':'min(remaining,16-(offset&15)); slave=(A0+2*((offset>>8)&FF))&FF; one low address byte',
            'page_checks':pages,'frame_checks':frames,'full_slot_checks':len(slots),'validated_save_checks':validated,'slots':slots,
            'frame':'0707: FF5E receives slave, low address and count payload bytes; FF55 final command=C0+2*count for count 1..16, mode1.',
            'status':'0707 waits for FF5D.bit5 before FIFO setup and FF5D.bit0 after launch; each waits up to 600 decrement passes. Successful return writes old FF5D|07 and sets carry.',
            'poll':'14CC -> 0:6C06, mode1 sends same slave then zero byte; waits for FF5D.bit0 up to 240 decrement passes. Caller retries at most 50 poll calls per page.',
            'pin':'FE08=0 before frame, restored to 1 after page success or any checked failure; zero-length does not touch FE08.',
            'mux':{'entry':'0FB0 -> 8:EAFE','checks':mux,'selector_0B':'1019=80, 1032=0, 1033=0; leaves 101A unchanged','reference_role':'RL6492 reference names selector11 _HW_IIC_PIN_40_41; 1019 value80 is _PIN_40_EEIICSCL. ASUS PCB wiring unproved.'},
            'failure_checks':failures,
            'reference':{'repo':'Kingdomwhisky/RTD-Scaler-TEST','commit':'3d38340ec8518a8888fd5d8dbb181c2a7418e11c','file':'Kernel/Scaler/RL6492_Series_Scaler/Code/RL6492_Series_Mcu.c','registers':'FF55/57/58 I2CM control, FF5D status, FF5E transmit data; FE08 PORT50'},
            'limits':['Entirely offline bytearray execution; no monitor/storage access.',
                      'Page checks explicitly model only 0707/14CC successful carry at call boundaries; separate frame/slot checks execute both routines with synthetic FF5D values.',
                      'Synthetic peripheral status is not I2C bus simulation, real ACK proof or storage completion.',
                      'EEPROM/page-write and FE08 write-protect roles are strong evidence; physical chip/pins and legal capacity unproved.',
                      'Only the configuration initialized by 01D0 is mapped; alternative modes of 0226/0707 are not complete.',
                      'Bank model, timers/physical delays, interrupt effects and unsupported CPU flags retain interpreter qualifications.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('firmware',type=Path)
    parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args()
    result = build(args.firmware.read_bytes())
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print('Page/frame/slot/mux checks:',result['page_checks'],result['frame_checks'],result['full_slot_checks'],result['mux']['checks'])
    print('Failure checks:',len(result['failure_checks']))


if __name__ == '__main__':main()

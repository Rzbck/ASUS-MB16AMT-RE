"""Verify the V020 battery acquisition/conversion/filter/OSD chain offline.

Uses the existing bounded interpreter on original instruction bytes. I2C is
explicitly mocked at 0:6D00; rendering stops before hardware-facing 1922.
No DLL loading, device access, or firmware mutation.
"""
import argparse
import hashlib
import json
from pathlib import Path

from analyze_banked_abi import SHA, inventory, traverse, verified_jump_tables
from emulate_mcs51 import Machine


def curve(x):
    if x < 550: return 0
    if x < 2950: return (((x - 550) * 29 // 24) + 100) // 100
    if x < 8050: return (((x - 2950) * 56 // 51) + 2999) // 100
    if x < 9450: return (x + 550) // 100
    if x <= 10000: return 100
    return 255


def filtered(raw, cached, countdown):
    if cached == 255:
        cached = raw if raw <= 100 else 50
        if raw > 100: raw = 50
    if raw > 100: return cached, countdown
    if raw == cached: return raw, 0
    if countdown: return cached, countdown - 1
    return cached + (1 if raw > cached else -1), 12


class Acquisition(Machine):
    def __init__(self, data, thunks, first, second, failures=0):
        super().__init__(data, thunks)
        self.payload = first.to_bytes(2, 'little') + second.to_bytes(2, 'little')
        self.failures, self.attempts = failures, 0

    def jump(self, target, call=False):
        if self.bank == 0 and target == 0x6D00:
            assert call
            assert (self.r(7), self.r(5), self.r(2), self.r(3)) == (0xAA, 1, 0, 0x10)
            assert self.x[0xD83E:0xD843] == bytes.fromhex('00 04 01 d8 29')
            self.attempts += 1
            self.c = self.attempts > self.failures
            if self.c: self.x[0xD829:0xD82D] = self.payload
            return
        super().jump(target, call)


class RenderDone(Exception):
    pass


class Renderer(Machine):
    def jump(self, target, call=False):
        if target == 0x1922:
            assert not call and self.bank == 10
            raise RenderDone()
        super().jump(target, call)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('firmware', type=Path)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--quick', action='store_true', help='Boundary subset instead of exhaustive 16-bit curve inputs')
    args = ap.parse_args()
    data = args.firmware.read_bytes()
    if hashlib.sha256(data).hexdigest() != SHA: raise SystemExit('Wrong V020 image')
    thunks = inventory(data)
    decoded, edges, indirect, reserved, overlaps = traverse(data, thunks)
    assert not reserved and not overlaps
    assert verified_jump_tables(data)[10, 0xD862][7][2] == 0xD8F4
    assert data[0x1E4C9:0x1E4CC] == bytes.fromhex('e7 6d 30')
    assert data[0x1E76D:0x1E777] == bytes.fromhex('12 cf 4c 74 a0 f0 a3 74 ef f0')
    # Decode the independently identified base-font battery warning.
    upper = 'ABCDEFGHIJKLMMNOPQRSTUVWWXYZ'
    lower = 'abcdefghijklmnopqrstuvwwxyz'
    glyphs = {i+11:c for i,c in enumerate(upper)} | {i+39:c for i,c in enumerate(lower)} | {0:' ', 0x4D:'!'}
    end = data.index(255, 0x1A0EF)
    warning = ''.join(glyphs[x] for x in data[0x1A0EF:end])
    assert warning == 'Out of battery soon!'

    bounds = [0,549,550,551,2949,2950,2951,8049,8050,8051,9449,9450,10000,10001,65535]
    count = 0
    for x in (bounds if args.quick else range(65536)):
        m = Machine(data, thunks)
        m.x[0xD828] = 255
        m.x[0xD82D:0xD82F] = x.to_bytes(2, 'big')
        actual = m.run(0, 0x5B0A, budget=4000)
        assert actual == curve(x), (x, actual, curve(x))
        assert {a for _,_,a in m.writes} <= {0xD828}
        count += 1

    acquisition_count = 0
    for first,second in [(0,0),(0,1000),(73,100),(98,100),(100,100),(10001,10000),(65535,1),(1,65535),(2949,10000),(2950,10000),(8050,10000),(9450,10000)]:
        for failures in (0,1,2):
            m = Acquisition(data, thunks, first, second, failures)
            result = m.run(0, 0x5A5C, budget=15000)
            expected = 255 if failures == 2 or second == 0 else curve((first*10000//second)&65535)
            assert result == expected, (first,second,failures,result,expected)
            acquisition_count += 1

    filter_count = 0
    for raw in (0,1,20,73,98,99,100,101,255):
        for cached in [*range(101),255]:
            for timer in (0,1,12):
                m = Machine(data, thunks)
                m.sr(7,raw); m.x[0xDCC2]=cached; m.x[0xDCC1]=timer
                actual = m.run(0,0x6EB9,budget=150)
                expected,counter = filtered(raw,cached,timer)
                assert (actual,m.x[0xDCC2],m.x[0xDCC1]) == (expected,expected,counter)
                filter_count += 1

    for value in range(101):
        m = Renderer(data, thunks)
        m.sr(7,3); m.sr(5,16); m.sr(3,value)
        try: m.run(10,0xF8F4,budget=3000)
        except RenderDone: pass
        else: raise AssertionError('Did not reach the string renderer')
        expected = bytes(int(c)+1 for c in str(value)) + b'\xff'
        assert m.x[0xD837:0xD837+len(expected)] == expected, value
        assert m.x[0xDCC6:0xDCC9] == bytes.fromhex('01 d8 37')
        assert m.x[0xD83F] == 0x3A

    # Cache sanitizer: every byte value, no device access.
    for value in range(256):
        m = Machine(data, thunks)
        m.x[0xD9F7] = value
        m.run(8, 0xF3D4, budget=40)
        assert m.x[0xD9F7] == (value if value <= 100 else 50)
        assert bool(m.c) == (value <= 100)
    # Shared storage ABI builder: offset 02BE, length 1, XDATA pointer D9F7.
    m = Machine(data, thunks)
    m.run(8, 0x99BA, budget=40)
    assert tuple(m.r(i) for i in (6,7,4,5,3,2,1)) == (2,190,0,1,1,217,247)
    for location in (0x9BFCC, 0x9C01B, 0xCF2EA):
        assert data[location:location+11] == bytes.fromhex('90 da 4c e0 90 d9 f7 f0 12 1a 8a')
    assert data[0x8F813:0x8F822] == bytes.fromhex('12 99 ba 12 19 4c 12 f3 d4 40 03 12 fe 89 22')
    assert data[0x8FE89:0x8FE92] == bytes.fromhex('12 f3 d4 12 99 ba 02 01 d0')
    assert data[0x9E7EF:0x9E7F8] == bytes.fromhex('12 cf a5 12 e7 03 12 16 2e')

    report = dict(cache_sanitizer_checks=256, cache_storage_offset='02BE',
        cache_field='D9F7', cache_storage_length=1,
        sha256=SHA, warning_text=warning,
        warning_selector='30', warning_branch='1:E76D', warning_trigger='10:D760(R7=7)',
        acquisition='0:5A5C -> 0:681E -> 0:6D00',
        slave_8bit='AA', slave_7bit='55', register='10', read_length=4,
        bus_pins={'clock':'FE0E / P5.6','data':'FE0F / P5.7'},
        raw_format='two little-endian unsigned 16-bit words; x=(first*10000//second)&FFFF',
        raw_percentage_return='0:5BAF R7; FF invalid', filter='0:6EB9; cached DCC2, countdown DCC1',
        runtime_displayed_field='DA4C', previous_field='DA4D', writer='9:E79E..E7A2',
        renderer='10:F8F4, R3 value; digits D837; pointer 01 D8 37; string id 3A -> 1:D7A1',
        curve_checks=count, acquisition_mock_checks=acquisition_count,
        filter_checks=filter_count, renderer_checks=101,
        cfg=dict(instructions=len(decoded),thunk_edges=len(edges),unresolved=len(indirect)),
        limitations=['Hardware acquisition mocked; no live DA4C value read.',
            'Fuel-gauge identity and physical units of the two words remain unproven.',
            'GPIO and warning classification use static code and reference register names.',
            'Logical-to-physical bank identity remains the existing working map.'])
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()

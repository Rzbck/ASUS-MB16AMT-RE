"""Verify the separate OSD cell-stream resolver and drawing port offline."""
import argparse
import hashlib
import json
from pathlib import Path
from analyze_banked_abi import SHA, inventory, verified_jump_tables
from emulate_mcs51 import Machine


class PortMachine(Machine):
    def __init__(self, *args):
        super().__init__(*args)
        self.port_bytes = []

    def writex(self, address, value):
        if address == 0x92:
            self.port_bytes.append(value & 255)
        super().writex(address, value)


class Selected(Exception):
    pass


def stream_model(payload, row, column, stride):
    """Independent model for ordinary cells, FE and FD with nonzero counts."""
    initial_column = column
    draws = []
    pos = 0
    def draw(glyph, suppress_wrap):
        nonlocal row, column
        draws.append((row, column, glyph))
        column = (column+1) & 255
        if column == stride and not suppress_wrap:
            row = (row+1) & 255
            column = initial_column
    while payload[pos] != 255:
        token = payload[pos]
        if token == 254:
            row = (row+1) & 255
            column = initial_column
            pos += 1
        elif token == 253:
            count = payload[pos+1]
            assert count > 0 and pos > 0
            for _ in range(count-1):
                draw(payload[pos-1], count == 254)
            pos += 2
        else:
            draw(token, payload[pos+1] == 254)
            pos += 1
    return draws, row, column, pos


def build(data):
    assert len(data) == 0xE0000 and hashlib.sha256(data).hexdigest() == SHA
    thunks = inventory(data)
    chunk = data[65536:131072]
    indexed = {0x3F:0xC66F, 0x44:0xC773, 0x45:0xC9F9,
               0x46:0xC919, 0x48:0xCA3D, 0x4A:0xCA88, 0x5C:0xC699}
    fixed = {s:0xC6A2+2*(s-0x4C) for s in range(0x4C,0x5A)}
    fixed.update({0x47:0xCA05, 0x49:0xCA40, 0x5A:0xC6BF, 0x5B:0xC6C2})
    resources = []
    for selector in range(256):
        for index in (0, 1):
            m = Machine(data, thunks)
            m.sr(7, selector); m.sr(5, index)
            m.run(1, 0xEEED, budget=500)
            actual = tuple(m.x[0xD840:0xD843])
            if selector in indexed:
                base = indexed[selector] + 3*index
                expected = tuple(chunk[base:base+3])
            elif selector in fixed:
                expected = (255, fixed[selector] >> 8, fixed[selector] & 255)
            else:
                expected = (0, 0, 0)
            assert actual == expected, (selector, index, actual, expected)
            assert (m.r(3), m.r(2), m.r(1)) == actual
            assert {a for _, _, a in m.writes} <= {0xD840, 0xD841, 0xD842}
            resources.append({'R7':f'{selector:02X}', 'R5':index,
                              'tag':f'{actual[0]:02X}',
                              'address':f'{actual[1]*256+actual[2]:04X}'})
    # Whole drawing leaf, including real address and port instructions.
    # Register writes use memory; this does not emulate the peripheral itself.
    draws = 0
    for row in range(256):
        for column, glyph, color in ((0,0,0), (17,77,1), (255,235,255)):
            m = PortMachine(data, thunks)
            m.sr(7,row); m.sr(5,column); m.sr(3,glyph)
            m.x[0xD841] = color
            m.x[0xDC09] = 25; m.x[0xDBFC] = 31
            m.x[0xDC04:0xDC06] = bytes.fromhex('12 34')
            m.x[0xDBF9:0xDBFB] = bytes.fromhex('20 80')
            m.x[0x94] = 0x15; m.x[0x90] = 0x80
            m.run(8, 0xD83D, budget=1000)
            address = (0x1234 + 25*row + column if row < 100 else
                       0x2080 + 31*(row-100) + column) & 65535
            assert m.x[0x90] == 0x80 | ((address >> 8) & 0x7F)
            assert m.x[0x91] == address & 255
            assert m.x[0x94] == (0x15 & 0x13) | 0xE8
            assert m.port_bytes == [0xC0, glyph, (color & 3)*0x55]
            assert {a for _, _, a in m.writes} <= {
                0xD840,0xD842,0xD843,0xD844,0xD845,0xD84D,
                0xD852,0xD853,0xD892,0x90,0x91,0x92,0x94}
            draws += 1
    # Synthetic RAM streams enter after pointer resolution; no patched image.
    class Stream(PortMachine):
        def __init__(self, *args):
            super().__init__(*args)
            self.cells = []
        def jump(self, target, call=False):
            if target == 0x1AA8:
                self.cells.append((self.r(7),self.r(5),self.r(3)))
            super().jump(target,call)
    payloads = [bytes([255]), bytes([11,12,13,14,255]),
                bytes([11,12,254,13,255]), bytes([254,254,11,255])]
    payloads += [bytes([11,253,n,12,254,13,255]) for n in (1,2,3,8,12,254)]
    stream_checks = 0
    for row in (1,99,100,254):
        for column in (0,1,2):
            for payload in payloads:
                m = Stream(data,thunks)
                m.x[0x9000:0x9000+len(payload)] = payload
                m.x[0xD83B:0xD83E] = bytes.fromhex('01 90 00')
                m.x[0xD833] = row; m.x[0xD834] = column
                m.x[0xD83A] = column; m.x[0xD838] = 3
                m.x[0xD837] = 2
                m.x[0xDC09] = 3; m.x[0xDBFC] = 3
                expected, end_row, end_col, consumed = stream_model(payload,row,column,3)
                m.run(1,0xF7E7,budget=500000)
                assert m.cells == expected, (row,column,payload.hex(),m.cells[:12],expected[:12])
                assert m.port_bytes == [v for _,_,glyph in expected for v in (0xC0,glyph,0xAA)]
                assert (m.x[0xD833],m.x[0xD83A]) == (end_row,end_col)
                assert int.from_bytes(m.x[0xD83C:0xD83E],'big') == 0x9000+consumed
                stream_checks += 1
    # Execute only the menu dispatch, halting before any category handler.
    targets = [target for _, _, target in verified_jump_tables(data)[10,0xB0B3]]
    assert targets == [0xB0CF,0xB16B,0xB1D1,0xB217,0xB265,
                       0xB2CA,0xB37F,0xB411,0xB440]
    class Dispatch(Machine):
        def jump(self, target, call=False):
            if target in targets or target == 0xB572:
                self.target = target
                raise Selected
            super().jump(target, call)
    for value in range(256):
        m = Dispatch(data, thunks); m.x[0xD823] = value
        try:
            m.run(10,0xB0A1,budget=50)
        except Selected:
            pass
        else:
            raise AssertionError('Expected category boundary')
        assert m.target == (targets[value] if value < 9 else 0xB572)
        assert not m.writes
    # Getter -> category scratch, including all high-nibble combinations.
    class Getter(Machine):
        def writex(self, address, value):
            super().writex(address, value)
            if (self.bank,self.origin,address) == (10,0xB048,0xD823):
                raise Selected
    for value in range(256):
        m = Getter(data, thunks); m.x[0xDA0A] = value; m.a = 0
        try:
            m.run(10,0xB03E,budget=1000)
        except Selected:
            pass
        else:
            raise AssertionError('Expected getter boundary')
        assert m.x[0xD823] == value & 15
    # Real helper fall-through: B613 writes family/index and continues into
    # B617, returning DA03&3F in A. Keep this separate from legal enum bounds.
    class Language(Machine):
        def readx(self, address):
            if (self.bank,self.origin,address) in ((1,0xDC87,0xD855),
                                                  (1,0xD30F,0xD865)):
                self.selected_language = self.x[address]
                raise Selected
            return super().readx(address)
    language_checks = 0
    for packed in range(256):
        for index in (0,1,4):
            for renderer, field, finish in ((0xDC4F,0xD853,0xBA0A),
                                             (0xD2D8,0xD863,0xBE58)):
                m = Language(data,thunks)
                m.x[0xDA03] = packed
                m.sr(6,index); m.a = 3; m.dptr = field
                m.run(10,0xB613,budget=30)
                assert m.a == packed & 63
                assert tuple(m.x[field:field+2]) == (3,index)
                m.run(10,finish,budget=30)
                assert m.x[field+2] == packed & 63
                m.sr(7,5); m.sr(5,2)
                try:
                    m.run(1,renderer,budget=1000)
                except Selected:
                    pass
                else:
                    raise AssertionError('Expected language boundary')
                assert m.selected_language == packed & 63
                language_checks += 1
    return {'firmware_sha256':SHA,
            'cell_resolver':{'entry':'1:EEED', 'input':'R7 selector, R5 index',
                'return':'R3:R2:R1 = D840..D842', 'checks':len(resources),
                'indexed_tables':{f'{s:02X}':f'1:{base:04X}' for s,base in indexed.items()},
                'fixed_resources':{f'{s:02X}':f'1:{base:04X}' for s,base in fixed.items()},
                'entries':resources},
            'cell_draw':{'entry':'8:D83D -> 6:F851 -> 8:EE13 -> 13:6137',
                'inputs':'R7 row, R5 column, R3 glyph, D841 color', 'checks':draws,
                'address':'row<100: BE16(DC04)+DC09*row+column; else: BE16(DBF9)+DBFC*(row-100)+column; modulo 65536',
                'port':'0092', 'payload':'C0, glyph, (color & 3)*55h',
                'address_registers':'0090 low 7 bits = address high byte masked to 7F; preserve bit7; 0091=low byte',
                'control':'0094 = (old & 13h) | E8h'},
            'cell_stream':{'entry':'1:F7E7 inside 1:F7B2','checks':stream_checks,
                'input':'D83B..D83D generic pointer; D833 row; D834 initial column; D83A current column; D838 stride; D837 color',
                'ordinary':'Draw current byte via 8:D83D and increment column',
                'FE':'Increment row and reset current column to D834',
                'FD':'Read count from next byte; emit previous stream byte count-1 further times, then consume FD/count',
                'FF':'Return without drawing terminator',
                'wrap':'When incremented column equals D838, advance row/reset column unless next byte is FE. In FD loop the compared next byte is the count.',
                'coverage':'10 synthetic streams × 4 starting rows × 3 starting columns; FD counts 1,2,3,8,12,254; empty stream, consecutive FE, automatic wrap and row-byte wrap'},
            'category_dispatch':{'entry':'10:B0A1','input':'D823', 'checks':256,
                'source':'10:B03E: query 8:5FEF(R7=0C,R5=0) -> DA0A & 0F -> D823 at B048',
                'source_checks':256,
                'targets':{str(i):f'10:{target:04X}' for i,target in enumerate(targets)},
                'fallback':'10:B572 for D823>=9'},
            'menu_language_provenance':{'source':'DA03 & 3F at 10:B617',
                'helper':'10:B613 writes family/index, then falls through B617 to return language in A',
                'paths':['10:B613 -> BA0A writes D855 -> 1:DC4F reads D855 at DC87 for segment count',
                         '10:B613 -> BE58 writes D865 -> 1:D2D8 reads D865 at D30F for segment count'],
                'checks':language_checks,
                'coverage':'256 packed DA03 values × 3 family-03 indices (0,1,4) × 2 actual resolver/renderer prologues',
                'boundary':'Stops before segment traversal; this proves provenance but not validity of all 64 masked values'},
            'limits':['Resolver index bounds and resource visual identities remain unresolved.',
                      'Cell row/column names describe verified arithmetic, not measured screen coordinates.',
                      'Drawing checks use three column/glyph/color combinations per row and fixed distinct bases/strides.',
                      'Category handler effects, navigation and key sampling are not tested by this dispatch check.',
                      'Stream fixtures enter after resolver with a RAM pointer; real resource validity and FD count zero remain unclassified.',
                      'No device I/O, proprietary resource bytes or bitmap bytes are exported.']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('firmware',type=Path)
    p.add_argument('--out',type=Path,required=True)
    args = p.parse_args()
    result = build(args.firmware.read_bytes())
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print('Resolver:',result['cell_resolver']['checks'],
          'draws:',result['cell_draw']['checks'],
          'streams:',result['cell_stream']['checks'],
          'language:',result['menu_language_provenance']['checks'],
          'dispatch/getter:',result['category_dispatch']['checks'],
          result['category_dispatch']['source_checks'])


if __name__ == '__main__':
    main()

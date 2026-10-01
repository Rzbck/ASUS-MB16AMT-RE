"""Verify OSD common glyph widths and byte-output address arithmetic offline."""
import argparse
import hashlib
import json
from pathlib import Path
from analyze_banked_abi import SHA, inventory
from emulate_mcs51 import Machine


class FontOutput(Machine):
    def __init__(self,*args):
        super().__init__(*args)
        self.port_bytes=[]

    def writex(self,address,value):
        if address==0xFF06:
            self.port_bytes.append(value&255)
        super().writex(address,value)


def extended_dispatch(data, thunks):
    # (bank, width base, narrow doubling): narrow ADD A,A loses glyph bit7.
    widths = {
        14:{251:(11,0xF2F5,False),252:(11,0xF4D7,False),253:(11,0xF6B9,True)},
        15:{251:(5,0xA487,False),252:(5,0xA669,False),253:(5,0xA84B,True)},
        16:{251:(5,0xA929,False),252:(5,0xAB0B,False),253:(5,0xACED,True)},
        17:{251:(2,0xC8CF,False),252:(2,0xCAB1,False)},
        18:{251:(2,0xCC87,False),252:(2,0xCE5F,False),253:(2,0xD051,False),
            254:(2,0xD231,False),249:(2,0xD387,True)},
        19:{251:(0,0xF0AF,False),252:(0,0xF293,False),253:(0,0xF475,False),
            254:(0,0xF65F,False),249:(0,0xF825,False),248:(0,0xFA01,True)}}
    fonts = {
        14:{251:(11,0xB23E),252:(11,0xCB8E),253:(11,0xE4DE)},
        15:{251:(5,0x2DC4),252:(5,0x4714),253:(5,0x6064)},
        16:{251:(5,0x6BFE),252:(5,0x854E),253:(5,0x9E9E)},
        17:{251:(2,0x2DC4),252:(2,0x4714)},
        18:{251:(2,0x5FC2),252:(2,0x788B),253:(2,0x92B3),
            254:(2,0xABE8),249:(2,0xBDD6)},
        19:{251:(0,0x7002),252:(0,0x896D),253:(0,0xA2BD),
            254:(0,0xBC79),249:(0,0xD44F),248:(0,0xEE77)}}
    width_checks = 0
    for language in range(21):
        for prefix in range(0xF8,0xFF):
            for glyph in range(256):
                m = Machine(data,thunks)
                m.sr(7,language);m.sr(5,prefix);m.sr(3,glyph)
                actual = m.run(1,0xFCE6,budget=1000)
                if prefix == 0xFA:
                    spec = (11,0xF11B,False)
                else:
                    spec = widths.get(language,{}).get(prefix)
                if spec:
                    bank,base,narrow = spec
                    offset = (2*glyph)&255 if narrow else 2*glyph
                    expected = min(12,max(4,data[bank*65536+base+offset]))
                elif 14 <= language <= 19:
                    expected = 12
                else:
                    expected = language  # untouched incoming R7 at dispatcher RET
                assert actual == expected,(language,prefix,glyph,actual,expected)
                assert {a for _,_,a in m.writes} <= set(range(0xD88E,0xD895))
                width_checks += 1
    output_checks = 0
    # Actual renderer output, all mapped extension tables and shared FA route.
    for language in range(21):
        for prefix,(bank,base) in {0xFA:(11,0x995A),**fonts.get(language,{})}.items():
            for glyph in range(8):
                for triplet in range(9):
                    m = FontOutput(data,thunks)
                    m.x[0xD842] = language; m.x[0xD866] = prefix
                    m.ram[0x29] = glyph; m.ram[0x26] = triplet
                    m.run(1,0xDBCA,budget=1000)
                    address = bank*65536+base+27*glyph+3*triplet
                    assert m.port_bytes == list(data[address:address+3])
                    assert {a for _,_,a in m.writes} <= set(range(0xD88E,0xD899)) | {0xFF06}
                    output_checks += 1
    tables = []
    for language,prefixes in widths.items():
        for prefix,(bank,base,narrow) in prefixes.items():
            font_bank,font_base = fonts[language][prefix]
            tables.append({'language_index':language,'prefix':f'{prefix:02X}',
                           'width_base':f'{bank}:{base:04X}',
                           'width_offset':'(2*glyph)&FF' if narrow else '2*glyph',
                           'font_base':f'{font_bank}:{font_base:04X}'})
    return {'width_checks':width_checks,'font_output_triplet_checks':output_checks,
            'tables':tables,'common_FA':'All 21 language indices use width 11:F11B and font 11:995A',
            'width_coverage':'21 stored language indices × 7 prefixes F8..FE × 256 glyph inputs',
            'output_coverage':'FA for all 21 indices plus all 22 extension tables; glyphs 0..7, triplets 0..8',
            'width_fallback':'For non-FA: indices 0E..13 return default 12 if no table matches; indices 00..0D and 14 return incoming language byte in R7 unchanged.',
            'limits':['Width inputs above table/enum bounds are mechanical tests, not valid text resources.',
                      'Narrow width arithmetic aliases glyph codes differing by 80h; legal limits remain open.',
                      'Font output tests cover mapped bases; no-table byte lookup paths are not asserted valid.',
                      'Language names, glyph images and physical SRAM/pixel layout remain unresolved.']}


def build(data):
    assert len(data)==0xE0000 and hashlib.sha256(data).hexdigest()==SHA
    thunks=inventory(data)
    widths=[]
    for glyph in range(256):
        m=Machine(data,thunks)
        m.sr(7,0);m.sr(5,0xFA);m.sr(3,glyph)
        actual=m.run(1,0xFCE6,budget=500)
        raw=data[11*65536+0xF11B+2*glyph]
        assert actual==min(12,max(4,raw)),(glyph,actual,raw)
        assert {a for _,_,a in m.writes} <= {0xD88E,0xD88F,0xD890}
        widths.append(actual)
    output_checks=0
    # Common table: check every 27-byte cell before the next resolved font base.
    # This interval test does not establish that every code is a legal OSD glyph.
    for prefix,base,glyphs in [(0xFA,0x995A,range(236)),
                              (0xFB,0xB23E,range(8)),
                              (0xFC,0xCB8E,range(8)),
                              (0xFD,0xE4DE,range(8))]:
        for glyph in glyphs:
            for triplet in range(9):
                m=FontOutput(data,thunks)
                m.x[0xD842]=0x0E
                m.x[0xD866]=prefix
                m.ram[0x29]=glyph
                m.ram[0x26]=triplet
                m.run(1,0xDBCA,budget=1000)
                offset=27*glyph+3*triplet
                expected=data[11*65536+base+offset:11*65536+base+offset+3]
                assert m.port_bytes==list(expected),(prefix,glyph,triplet)
                assert {a for _,_,a in m.writes} <= {0xD88E,0xD88F,0xD890,0xD891,0xFF06}
                output_checks+=1
    # Verify the row loop guard independent from glyph fetch and layout writes.
    for old in range(256):
        m=Machine(data,thunks)
        m.a=0xD8;m.ram[0x82]=0x43;m.sr(7,0);m.ram[0x26]=old
        m.run(1,0xD11D,budget=20)
        count=(old+1)&255
        assert m.ram[0x26]==count and m.c==(count<9)
    return {'firmware_sha256':SHA,
            'extended_dispatch':extended_dispatch(data,thunks),
            'common_width':{'entry':'1:FCE6 -> 11:FD9D','inputs':'R7=0, R5=FA, R3=glyph',
                'formula':'clamp(code[11:F11B + 2*glyph], 4, 12)',
                'return':'R7','checks':256,'values_for_all_byte_inputs':widths},
            'font_output':{'entry':'1:DBCA','inputs':'D842=0E, D866=prefix, RAM 29h=glyph, RAM 26h=triplet',
                'formula':'bank 11 font base + 27*glyph + 3*triplet, three consecutive bytes to FF06',
                'prefix_bases':{'FA':'11:995A','FB':'11:B23E','FC':'11:CB8E','FD':'11:E4DE'},
                'checks':output_checks,'common_glyph_inputs_checked':'00..EB',
                'extension_glyph_inputs_checked':'00..07','triplets_checked':'0..8'},
            'triplet_loop':{'guard':'1:D11D','rule':'increment RAM 26h, continue while resulting byte <9',
                'checks':256,'storage_bytes_per_full_cell':27},
            'limits':['Input ranges tested are mechanical contracts, not proof of legal glyph enum bounds.',
                      'Peripheral writes are recorded in memory; port setup, compression and displayed pixels are not emulated.',
                      'No font bitmap bytes are exported. Legal glyph bounds and pixel layout remain unresolved.']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('firmware',type=Path);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();result=build(args.firmware.read_bytes())
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print('Widths:',result['common_width']['checks'],'output triplets:',result['font_output']['checks'],
          'loop guard:',result['triplet_loop']['checks'])
    print('Extended widths/output:',result['extended_dispatch']['width_checks'],
          result['extended_dispatch']['font_output_triplet_checks'])


if __name__=='__main__':main()

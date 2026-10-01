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
                      'No font bitmap bytes are exported. Other language banks remain to be mapped.']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('firmware',type=Path);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();result=build(args.firmware.read_bytes())
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print('Widths:',result['common_width']['checks'],'output triplets:',result['font_output']['checks'],
          'loop guard:',result['triplet_loop']['checks'])


if __name__=='__main__':main()

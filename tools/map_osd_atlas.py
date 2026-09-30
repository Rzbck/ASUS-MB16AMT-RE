"""Build a SHA-pinned, offline OSD event/resource atlas using existing decoders.

Resource execution covers all R7 selectors with R5=0 and R5=1; this does not
claim exhaustive coverage of other arguments, languages or rendering behavior.
No firmware bytes, glyph bitmaps, device identifiers or binaries are exported.
"""
import argparse
import hashlib
import json
from pathlib import Path
from analyze_banked_abi import SHA, inventory, traverse, verified_jump_tables
from emulate_mcs51 import Machine


def build(data):
    if len(data) != 0xE0000 or hashlib.sha256(data).hexdigest() != SHA:
        raise ValueError('Expected verified ASUS V020')
    thunks = inventory(data)
    decoded, edges, indirect, reserved, overlaps = traverse(data, thunks)
    assert not reserved and not overlaps
    tables = verified_jump_tables(data)
    upper = 'ABCDEFGHIJKLMMNOPQRSTUVWWXYZ'
    lower = 'abcdefghijklmnopqrstuvwwxyz'
    glyphs = {i+11:c for i,c in enumerate(upper)} | {i+39:c for i,c in enumerate(lower)}
    glyphs.update({i+1:str(i) for i in range(10)})
    glyphs.update({0:' ', 0x42:'.', 0x4D:'!'})
    resources = []
    for selector in range(256):
        for arg5 in (0, 1):
            m = Machine(data, thunks)
            m.sr(7, selector)
            m.sr(5, arg5)
            m.x[0xDCC6:0xDCC9] = bytes.fromhex('01 D8 37')
            m.run(1, 0xE43B, budget=5000)
            pointer = bytes(m.x[0xD893:0xD896])
            assert (m.r(3),m.r(2),m.r(1)) == tuple(pointer)
            assert {a for _,_,a in m.writes} <= {0xD893,0xD894,0xD895}
            address = int.from_bytes(pointer[1:], 'big')
            row = {'selector':f'{selector:02X}', 'input_R5':arg5,
                   'pointer_tag':f'{pointer[0]:02X}', 'address':f'{address:04X}',
                   'steps':m.steps}
            if pointer[0] == 0xFF:
                # All code reads in this resolver use the statically modeled bank 1.
                chunk = data[65536:131072]
                end = chunk.find(b'\xff', address, min(address+192,65536))
                if end >= address:
                    row['first_segment_base_font_candidate'] = ''.join(
                        glyphs.get(x,f'<{x:02X}>') for x in chunk[address:end])
                    row['first_segment_length'] = end-address
            resources.append(row)
    warning = next(r for r in resources if r['selector']=='30' and r['input_R5']==0)
    assert warning['address']=='A0EF'
    assert warning['first_segment_base_font_candidate']=='Out of battery soon!'
    timer = [{'event_R7':f'{index+1:02X}', 'entry':f'4:{entry:04X}',
              'target':f'4:{target:04X}'} for index,entry,target in tables[4,0xEC36]]
    assert timer[0x17-1]['target']=='4:EFDB'
    assert (4,0xF058) in decoded
    return {'firmware_sha256':SHA,
            'bank_model':'Existing logical/physical static identity assumption; not a new hardware proof.',
            'counts':{'decoded_instructions':len(decoded),'unresolved_indirect_sites':len(indirect),
                      'verified_jump_tables':len(tables),'resource_executions':len(resources)},
            'timer_dispatch':{'entry':'4:EC1F','jump':'4:EC36','events':timer},
            'resource_resolver':{'entry':'1:E43B','selector':'R7','additional_argument':'R5; semantics unresolved',
                'return':'R3:R2:R1 generic pointer, also D893..D895',
                'writes':['D893','D894','D895'], 'entries':resources},
            'limits':['Base-font text candidates only; unknown glyphs are preserved as tokens.',
                      'First FF-terminated segment only; language indexing and token effects unresolved.',
                      '512 argument cases, not an exhaustive ABI proof.',
                      'CFG reachability is static, not evidence that a path runs on the monitor.']}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('firmware',type=Path)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    result=build(args.firmware.read_bytes())
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/'osd-atlas.json').write_text(json.dumps(result,indent=2)+'\n')
    rows=result['resource_resolver']['entries']
    text=['# OSD resource resolver: derived index','',
          'R5=0 cases only below. Text is a partial base-font decoding, not an ASCII firmware string.',
          'Unknown glyphs remain hexadecimal tokens. See osd-atlas.json for R5=1 cases and limits.','',
          '| Selector | Pointer tag | Address | First segment candidate |',
          '|---|---|---|---|']
    for r in rows:
        if r['input_R5']==0 and (r['selector'] <= '3F' or r['pointer_tag']!='00'):
            label=r.get('first_segment_base_font_candidate','(dynamic or no bounded terminator)')
            text.append('| '+ ' | '.join([r['selector'],r['pointer_tag'],r['address'],label.replace('|','\\|')])+' |')
    (args.out/'osd-resource-index.md').write_text('\n'.join(text)+'\n')
    print(json.dumps(result['counts']))


if __name__=='__main__':
    main()

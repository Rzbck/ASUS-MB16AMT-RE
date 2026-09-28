"""Verify the V020 numeric-renderer candidate; output derived metadata only.

Read-only input, no hardware access. Uses the adjacent ABI analyzer (stdlib).
This identifies a formatting routine, NOT a battery/SOC source.
"""
from pathlib import Path
import argparse
import hashlib
import json
from analyze_banked_abi import SHA, BANK_SIZE, hits, inventory, traverse


def analyze(data):
    if len(data) != 0xE0000 or hashlib.sha256(data).hexdigest() != SHA:
        raise ValueError('Expected the verified ASUS V020 image')
    thunks = inventory(data)
    assert thunks[0x1670] == (1, 0xEAEB)
    # Independently check the relevant small sequences, not a bulk byte dump.
    checks = {
        0xCF81: '7b a0 7a 86 79 01 78 00',  # divisor 100000
        0xCF89: '90 d8 38 e0 fc a3 e0 fd a3 e0 fe a3 e0 ff 02 1f b9',
        0xEB51: '7b 10 7a 27 12 d1 7c',  # divisor 10000
        0xEB69: '7b e8 7a 03 12 d1 7c',  # divisor 1000
        0xEB81: '7b 64 12 d1 7b',  # divisor 100
        0xEB96: '7b 0a 12 d1 7b',  # divisor 10
        0xD0D4: 'ac 00 ad 01 ae 02 af 03 e4 22',  # remainder -> next dividend
        0xD17B: 'fa f9 f8 12 1f b9 ef 04 22',  # quotient + glyph base 1
        0xD195: '90 dc c6 74 01 f0 a3 22',  # XDATA generic pointer tag
    }
    for addr, signature in checks.items():
        expected = bytes.fromhex(signature)
        actual = data[BANK_SIZE + addr:BANK_SIZE + addr + len(expected)]
        assert actual == expected, f'Candidate check failed at 1:{addr:04X}'
    decoded, edges, indirect, reserved, overlaps = traverse(data, thunks)
    callers = []
    for bank in range(14):
        chunk = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
        for op, kind in ((0x12, 'LCALL'), (0x02, 'LJMP')):
            for site in hits(chunk, bytes([op, 0x16, 0x70])):
                callers.append({'physical_bank': bank, 'site': f'{site:04X}', 'kind': kind,
                                'cfg_boundary': (bank, site) in decoded})
    return {
        'sha256': SHA, 'status': 'STRONG EVIDENCE: numeric OSD renderer, not SOC identification',
        'candidate': 'logical 1:EAEB', 'thunk': '1670',
        'reference': 'RTD2014OsdFontProp.c:OsdPropShowNumber, commit 3d38340ec8518a8888fd5d8dbb181c2a7418e11c',
        'input_unsigned_value_xdata': 'D838..D83B (big-endian)',
        'format_flags_xdata': 'D83C', 'digit_buffer_xdata': 'D840..D845 (least significant first)',
        'output_string_xdata': 'D848 onward', 'output_pointer_xdata': 'DCC6..DCC8 (01 D8 48)',
        'divisors': [100000, 10000, 1000, 100, 10],
        'glyph_digit_bias': 1, 'terminator': 'FF', 'raw_callers': callers,
        'limits': 'Two callers reached from ABI seeds; 4:F058 is a coherent manual candidate not reached by this CFG. No assertion that DA86 or D82E..D82F is battery state.',
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('firmware', type=Path)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    result = analyze(args.firmware.read_bytes())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

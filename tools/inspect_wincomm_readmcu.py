"""Inspect WinComm.dll's ReadMcuReg export without loading or calling the DLL.

This is a read-only PE parser using only the Python standard library. It prints
matching exports, the exact export RVA/file offset, nearby export RVAs, a short
hex dump of the function body, simple x86 stack-reference clues, and RET forms.

Purpose: validate the native ABI/signature before making any further runtime
ReadMcuReg calls. No device I/O is performed.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import struct


def u16(b: bytes, o: int) -> int:
    return struct.unpack_from('<H', b, o)[0]


def u32(b: bytes, o: int) -> int:
    return struct.unpack_from('<I', b, o)[0]


def cstr(b: bytes, o: int) -> str:
    e = b.find(b'\0', o)
    if e < 0:
        e = len(b)
    return b[o:e].decode('ascii', errors='replace')


class PE:
    def __init__(self, data: bytes):
        self.data = data
        if data[:2] != b'MZ':
            raise ValueError('Not an MZ executable')
        pe = u32(data, 0x3C)
        if data[pe:pe+4] != b'PE\0\0':
            raise ValueError('Missing PE signature')
        coff = pe + 4
        self.machine = u16(data, coff)
        self.nsects = u16(data, coff + 2)
        self.opt_size = u16(data, coff + 16)
        opt = coff + 20
        magic = u16(data, opt)
        if magic == 0x10B:  # PE32
            dd = opt + 96
            self.bits = 32
        elif magic == 0x20B:  # PE32+
            dd = opt + 112
            self.bits = 64
        else:
            raise ValueError(f'Unsupported optional-header magic 0x{magic:04X}')
        self.export_rva = u32(data, dd)
        self.export_size = u32(data, dd + 4)
        sect = opt + self.opt_size
        self.sections = []
        for i in range(self.nsects):
            o = sect + 40 * i
            name = data[o:o+8].split(b'\0', 1)[0].decode('ascii', errors='replace')
            vsize = u32(data, o + 8)
            va = u32(data, o + 12)
            raw_size = u32(data, o + 16)
            raw = u32(data, o + 20)
            self.sections.append((name, va, vsize, raw, raw_size))

    def rva_to_off(self, rva: int) -> int:
        for _name, va, vsize, raw, raw_size in self.sections:
            span = max(vsize, raw_size)
            if va <= rva < va + span:
                return raw + (rva - va)
        # headers can be addressed by RVA directly
        if 0 <= rva < len(self.data):
            return rva
        raise ValueError(f'RVA 0x{rva:X} not mapped')

    def export_records(self):
        if not self.export_rva:
            return []
        eo = self.rva_to_off(self.export_rva)
        base = u32(self.data, eo + 16)
        nfunc = u32(self.data, eo + 20)
        nname = u32(self.data, eo + 24)
        funcs = u32(self.data, eo + 28)
        names = u32(self.data, eo + 32)
        ords = u32(self.data, eo + 36)
        funcs_o = self.rva_to_off(funcs)
        names_o = self.rva_to_off(names)
        ords_o = self.rva_to_off(ords)
        by_index = {}
        for i in range(nname):
            nrva = u32(self.data, names_o + 4*i)
            name = cstr(self.data, self.rva_to_off(nrva))
            idx = u16(self.data, ords_o + 2*i)
            by_index[idx] = name
        out = []
        for idx in range(nfunc):
            rva = u32(self.data, funcs_o + 4*idx)
            if not rva:
                continue
            name = by_index.get(idx, '')
            forwarded = None
            if self.export_rva <= rva < self.export_rva + self.export_size:
                forwarded = cstr(self.data, self.rva_to_off(rva))
            out.append((name, base + idx, rva, forwarded))
        return out


def hex_dump(data: bytes, start: int, size: int = 128) -> list[str]:
    out = []
    chunk = data[start:start+size]
    for i in range(0, len(chunk), 16):
        row = chunk[i:i+16]
        hs = ' '.join(f'{x:02X}' for x in row)
        asc = ''.join(chr(x) if 32 <= x < 127 else '.' for x in row)
        out.append(f'{i:04X}: {hs:<47}  {asc}')
    return out


def x86_clues(code: bytes):
    clues = []
    # common 32-bit stack argument forms
    pats = {
        b'\x8B\x44\x24': 'MOV EAX,[ESP+imm8]',
        b'\x8B\x4C\x24': 'MOV ECX,[ESP+imm8]',
        b'\x8B\x54\x24': 'MOV EDX,[ESP+imm8]',
        b'\x8B\x5C\x24': 'MOV EBX,[ESP+imm8]',
        b'\x8A\x44\x24': 'MOV AL,[ESP+imm8]',
        b'\x0F\xB6\x44\x24': 'MOVZX EAX,byte [ESP+imm8]',
        b'\xFF\x74\x24': 'PUSH dword [ESP+imm8]',
        b'\x8D\x44\x24': 'LEA EAX,[ESP+imm8]',
    }
    for pat, desc in pats.items():
        p = 0
        while True:
            p = code.find(pat, p)
            if p < 0:
                break
            imm_pos = p + len(pat)
            if imm_pos < len(code):
                clues.append((p, f'{desc} imm=0x{code[imm_pos]:02X}'))
            p += 1
    for i, op in enumerate(code):
        if op == 0xC3:
            clues.append((i, 'RET (caller cleans stack: cdecl-like or no stack args)'))
        elif op == 0xC2 and i + 2 < len(code):
            n = code[i+1] | (code[i+2] << 8)
            clues.append((i, f'RET 0x{n:X} (callee cleans {n} bytes)'))
    return sorted(set(clues))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('path', type=Path, help='WinComm.dll or a directory containing it')
    ap.add_argument('--bytes', type=int, default=160, help='Function bytes to dump (default 160)')
    args = ap.parse_args()

    path = args.path
    if path.is_dir():
        hits = list(path.rglob('WinComm.dll'))
        if not hits:
            raise SystemExit(f'WinComm.dll not found under {path}')
        path = hits[0]
    data = path.read_bytes()
    pe = PE(data)
    exports = pe.export_records()

    print('ASUS MB16AMT — offline WinComm ReadMcuReg ABI inspection')
    print(f'file: {path}')
    print(f'size: {len(data)} bytes')
    print(f'PE: {pe.bits}-bit machine=0x{pe.machine:04X} sections={pe.nsects}')
    print('NO DLL LOAD; NO DEVICE I/O')
    print()

    interesting = [r for r in exports if any(k in r[0].lower() for k in ('read', 'mcu', 'reg', 'debug'))]
    print('===== RELEVANT EXPORTS =====')
    for name, ordinal, rva, fwd in sorted(interesting, key=lambda x: x[2]):
        extra = f' -> {fwd}' if fwd else ''
        print(f'ord={ordinal:4d} RVA=0x{rva:08X} {name or "<ordinal-only>"}{extra}')
    print()

    targets = [r for r in exports if 'readmcureg' in r[0].lower()]
    if not targets:
        print('No named export containing ReadMcuReg was found.')
        print('Do not make another runtime call until the actual export/caller is identified.')
        return 2

    for name, ordinal, rva, fwd in targets:
        print(f'===== TARGET {name} ord={ordinal} RVA=0x{rva:08X} =====')
        if fwd:
            print(f'Forwarded export: {fwd}')
            continue
        off = pe.rva_to_off(rva)
        print(f'file offset: 0x{off:08X}')
        same_section = []
        for rec in exports:
            if rec[3] is None and rec[2] != rva:
                same_section.append(rec)
        prevs = sorted((x for x in same_section if x[2] < rva), key=lambda x: x[2])[-3:]
        nexts = sorted((x for x in same_section if x[2] > rva), key=lambda x: x[2])[:3]
        print('-- nearby exports --')
        for rec in prevs + [(name, ordinal, rva, None)] + nexts:
            marker = ' <<<' if rec[2] == rva else ''
            print(f'RVA=0x{rec[2]:08X} ord={rec[1]:4d} {rec[0] or "<ordinal-only>"}{marker}')

        print('-- bytes --')
        n = max(32, min(args.bytes, 512))
        for line in hex_dump(data, off, n):
            print(line)

        print('-- simple x86 ABI clues --')
        clues = x86_clues(data[off:off+n])
        if not clues:
            print('(no simple stack/RET clues found in dumped window)')
        else:
            for pos, desc in clues:
                print(f'+0x{pos:03X}: {desc}')
        print()

    print('===== INTERPRETATION =====')
    print('A non-zero runtime value such as 0x2B08 must not be treated as a valid status/value until the native ABI is established.')
    print('Use the export decoration, RET form, and stack references above to determine the real parameter count/return convention before another probe.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

"""Find how ASUS updater binaries actually call WinComm!ReadRegEx.

Offline/read-only: parses PE import tables in EXE/DLL files under the supplied
firmware root, locates IAT calls to ReadRegEx, and prints raw x86 context around
each call. No DLL loading and no device I/O.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import struct


def u16(b, o): return struct.unpack_from('<H', b, o)[0]
def u32(b, o): return struct.unpack_from('<I', b, o)[0]


class PE:
    def __init__(self, path: Path):
        self.path = path
        self.b = path.read_bytes()
        if self.b[:2] != b'MZ':
            raise ValueError('not MZ')
        pe = u32(self.b, 0x3C)
        if self.b[pe:pe+4] != b'PE\0\0':
            raise ValueError('not PE')
        coff = pe + 4
        self.nsec = u16(self.b, coff + 2)
        opt = coff + 20
        magic = u16(self.b, opt)
        if magic != 0x10B:
            raise ValueError('not PE32')
        self.image_base = u32(self.b, opt + 28)
        self.size_headers = u32(self.b, opt + 60)
        self.dd = opt + 96
        sec = opt + u16(self.b, coff + 16)
        self.sections = []
        for i in range(self.nsec):
            o = sec + 40*i
            name = self.b[o:o+8].split(b'\0',1)[0].decode('ascii','replace')
            vsize, va, rawsz, raw = struct.unpack_from('<IIII', self.b, o+8)
            self.sections.append((name, va, max(vsize, rawsz), raw, rawsz))

    def rva_to_off(self, rva: int):
        if rva < self.size_headers:
            return rva
        for _, va, span, raw, rawsz in self.sections:
            if va <= rva < va + span:
                d = rva - va
                if d >= rawsz:
                    return None
                return raw + d
        return None

    def cstr_rva(self, rva: int):
        o = self.rva_to_off(rva)
        if o is None: return ''
        e = self.b.find(b'\0', o)
        if e < 0: e = min(len(self.b), o+256)
        return self.b[o:e].decode('ascii','replace')

    def imports(self):
        imp_rva = u32(self.b, self.dd + 8)
        if not imp_rva:
            return []
        o = self.rva_to_off(imp_rva)
        if o is None:
            return []
        out = []
        while True:
            oft, _, _, name_rva, ft = struct.unpack_from('<IIIII', self.b, o)
            if not any((oft, name_rva, ft)):
                break
            dll = self.cstr_rva(name_rva)
            thunk_rva = oft or ft
            to = self.rva_to_off(thunk_rva)
            if to is not None:
                idx = 0
                while True:
                    ent = u32(self.b, to + 4*idx)
                    if ent == 0: break
                    if ent & 0x80000000:
                        name = f'ord{ent & 0xFFFF}'
                    else:
                        no = self.rva_to_off(ent)
                        if no is None:
                            name = '?'
                        else:
                            end = self.b.find(b'\0', no+2)
                            name = self.b[no+2:end].decode('ascii','replace')
                    out.append((dll, name, ft + 4*idx))
                    idx += 1
            o += 20
        return out

    def executable_ranges(self):
        for name, va, span, raw, rawsz in self.sections:
            # Good enough for updater PE files: .text/code sections.
            if name.startswith('.text') or name.upper().startswith('CODE'):
                yield name, va, raw, rawsz


def hx(buf: bytes, base: int = 0):
    for i in range(0, len(buf), 16):
        c = buf[i:i+16]
        asc = ''.join(chr(x) if 32 <= x < 127 else '.' for x in c)
        print(f'{base+i:04X}: ' + ' '.join(f'{x:02X}' for x in c).ljust(47) + f'  {asc}')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('root', type=Path)
    args = ap.parse_args()

    files = sorted([p for p in args.root.rglob('*') if p.is_file() and p.suffix.lower() in ('.exe','.dll')])
    print('ASUS MB16AMT — offline vendor ReadRegEx caller inspection')
    print(f'root: {args.root}')
    print('NO DLL LOAD; NO DEVICE I/O')
    print()

    importers = 0
    calls = 0
    for p in files:
        try:
            pe = PE(p)
        except Exception:
            continue
        matches = [(dll,name,iat) for dll,name,iat in pe.imports() if name.lower() == 'readregex']
        if not matches:
            continue
        importers += 1
        print(f'===== {p.relative_to(args.root)} =====')
        print(f'ImageBase=0x{pe.image_base:08X}')
        for dll,name,iat_rva in matches:
            abs_iat = pe.image_base + iat_rva
            print(f'import {dll}!{name} IAT_RVA=0x{iat_rva:08X} abs=0x{abs_iat:08X}')
            needle = b'\xFF\x15' + struct.pack('<I', abs_iat)
            found_here = 0
            for secname, va, raw, rawsz in pe.executable_ranges():
                sec = pe.b[raw:raw+rawsz]
                pos = 0
                while True:
                    q = sec.find(needle, pos)
                    if q < 0: break
                    found_here += 1
                    calls += 1
                    call_rva = va + q
                    lo = max(0, q-64)
                    hi = min(len(sec), q+32)
                    print()
                    print(f'-- CALL [{dll}!{name}] at RVA=0x{call_rva:08X} section={secname} --')
                    hx(sec[lo:hi], base=q-lo)
                    print('call bytes are at context offset 0x%X' % (q-lo))
                    pos = q + 1
            if not found_here:
                print('(import present but no direct FF 15 IAT call found; may be copied to a function pointer or optimized differently)')
        print()

    if not importers:
        print('No PE file imports ReadRegEx by name.')
        print('Searching vendor binaries may require GetProcAddress/string-based resolution instead.')
    print('===== SUMMARY =====')
    print(f'importing binaries: {importers}')
    print(f'direct IAT call sites: {calls}')
    print('Use vendor call-site pushes/register setup as authoritative ABI/protocol evidence before another runtime probe.')


if __name__ == '__main__':
    main()

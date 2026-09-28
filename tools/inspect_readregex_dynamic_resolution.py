"""Inspect vendor PE files for dynamic WinComm/ReadRegEx resolution clues.

Offline only: reads PE files under the supplied firmware root. No DLL load and no device I/O.
Looks for ASCII/UTF-16 strings (ReadRegEx, WinComm.dll, GetProcAddress) and reports
nearby raw bytes plus PE imports of GetProcAddress/LoadLibrary. This is locator evidence,
not proof of a call until a control-flow site is reconstructed.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import struct

NEEDLES = [
    "ReadRegEx",
    "ReadRegsEx",
    "ReadReg",
    "WinComm.dll",
    "GetProcAddress",
    "LoadLibraryA",
    "LoadLibraryW",
]


def u16(data: bytes, off: int) -> int:
    return struct.unpack_from("<H", data, off)[0]


def u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def parse_pe(data: bytes):
    if len(data) < 0x100 or data[:2] != b"MZ":
        return None
    pe = u32(data, 0x3C)
    if pe + 0x100 > len(data) or data[pe:pe+4] != b"PE\0\0":
        return None
    machine = u16(data, pe + 4)
    nsec = u16(data, pe + 6)
    optsz = u16(data, pe + 20)
    opt = pe + 24
    magic = u16(data, opt)
    if magic != 0x10B:  # PE32 only for these vendor binaries
        return {"machine": machine, "sections": [], "imports": []}
    image_base = u32(data, opt + 28)
    dd = opt + 96
    import_rva = u32(data, dd + 8)
    import_size = u32(data, dd + 12)
    sections = []
    sh = opt + optsz
    for i in range(nsec):
        o = sh + i * 40
        name = data[o:o+8].split(b"\0",1)[0].decode("ascii", "replace")
        vsize = u32(data, o + 8)
        va = u32(data, o + 12)
        rawsz = u32(data, o + 16)
        raw = u32(data, o + 20)
        sections.append((name, va, max(vsize, rawsz), raw, rawsz))
    return {
        "machine": machine,
        "image_base": image_base,
        "import_rva": import_rva,
        "import_size": import_size,
        "sections": sections,
    }


def rva_to_off(pe, rva: int):
    for _name, va, span, raw, rawsz in pe["sections"]:
        if va <= rva < va + span:
            d = rva - va
            if d < rawsz:
                return raw + d
    return None


def cstr(data: bytes, off: int) -> str:
    end = data.find(b"\0", off)
    if end < 0:
        end = min(len(data), off + 512)
    return data[off:end].decode("ascii", "replace")


def imports(data: bytes, pe):
    out = []
    rva = pe.get("import_rva", 0)
    if not rva:
        return out
    off = rva_to_off(pe, rva)
    if off is None:
        return out
    for idx in range(4096):
        d = off + idx * 20
        if d + 20 > len(data):
            break
        oft, _ts, _fc, name_rva, ft = struct.unpack_from("<IIIII", data, d)
        if not any((oft, name_rva, ft)):
            break
        noff = rva_to_off(pe, name_rva)
        dll = cstr(data, noff) if noff is not None else f"rva_{name_rva:X}"
        thunk_rva = oft or ft
        toff = rva_to_off(pe, thunk_rva)
        if toff is None:
            continue
        for j in range(8192):
            q = toff + j * 4
            if q + 4 > len(data):
                break
            ent = u32(data, q)
            if ent == 0:
                break
            iat_rva = ft + j * 4
            if ent & 0x80000000:
                out.append((dll, f"#{ent & 0xFFFF}", iat_rva))
                continue
            hn = rva_to_off(pe, ent)
            if hn is None or hn + 2 >= len(data):
                continue
            name = cstr(data, hn + 2)
            out.append((dll, name, iat_rva))
    return out


def hexdump(data: bytes, center: int, radius: int = 48) -> str:
    a = max(0, center - radius)
    b = min(len(data), center + radius)
    lines = []
    for off in range(a, b, 16):
        chunk = data[off:min(off+16, b)]
        hx = " ".join(f"{x:02X}" for x in chunk)
        asc = "".join(chr(x) if 32 <= x < 127 else "." for x in chunk)
        mark = " <==" if off <= center < off + 16 else ""
        lines.append(f"{off:08X}: {hx:<47} {asc}{mark}")
    return "\n".join(lines)


def all_hits(data: bytes, s: str):
    encs = [("ascii", s.encode("ascii")), ("utf16le", s.encode("utf-16le"))]
    for kind, pat in encs:
        pos = 0
        while True:
            p = data.find(pat, pos)
            if p < 0:
                break
            yield kind, p
            pos = p + 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", type=Path)
    args = ap.parse_args()

    root = args.root
    print("ASUS MB16AMT — offline dynamic ReadRegEx resolution inspection")
    print(f"root: {root}")
    print("NO DLL LOAD; NO DEVICE I/O")
    print()

    files = sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in {".exe", ".dll"})
    total_hits = 0
    dynamic_candidates = 0

    for path in files:
        try:
            data = path.read_bytes()
        except OSError:
            continue
        pe = parse_pe(data)
        if not pe:
            continue
        imps = imports(data, pe)
        imp_names = {(dll.lower(), name) for dll, name, _iat in imps}
        gp = [(dll, name, iat) for dll, name, iat in imps if name == "GetProcAddress"]
        ll = [(dll, name, iat) for dll, name, iat in imps if name in {"LoadLibraryA", "LoadLibraryW", "LoadLibraryExA", "LoadLibraryExW"}]

        hits = []
        for needle in NEEDLES:
            for kind, off in all_hits(data, needle):
                hits.append((needle, kind, off))

        interesting = hits or gp or ll
        if not interesting:
            continue

        print(f"===== {path.relative_to(root)} =====")
        print(f"machine=0x{pe['machine']:04X} image_base=0x{pe.get('image_base',0):08X}")
        if gp:
            print("imports GetProcAddress:")
            for dll, name, iat in gp:
                print(f"  {dll}!{name} IAT_RVA=0x{iat:08X} VA=0x{pe['image_base']+iat:08X}")
        if ll:
            print("imports loader APIs:")
            for dll, name, iat in ll:
                print(f"  {dll}!{name} IAT_RVA=0x{iat:08X} VA=0x{pe['image_base']+iat:08X}")

        readregex_hits = [h for h in hits if h[0] == "ReadRegEx"]
        if readregex_hits and gp:
            dynamic_candidates += 1
            print("** dynamic-resolution candidate: ReadRegEx string + GetProcAddress import **")

        for needle, kind, off in hits:
            total_hits += 1
            print()
            print(f"-- string {needle!r} ({kind}) file_off=0x{off:08X} --")
            print(hexdump(data, off, 64))
        print()

    print("===== SUMMARY =====")
    print(f"PE files scanned: {len(files)}")
    print(f"string hits: {total_hits}")
    print(f"ReadRegEx + GetProcAddress candidates: {dynamic_candidates}")
    print("If a candidate exists, reconstruct only that resolver/call path next.")
    print("If none exists, stop pursuing ReadRegEx as a vendor-used API and identify the actual imported/read wrapper instead.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

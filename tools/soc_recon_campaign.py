"""Consolidated host-side SOC reconnaissance campaign for ASUS MB16AMT.

Offline/read-only. This script does NOT load vendor DLLs and does NOT access the monitor.
It replaces the former one-question-at-a-time probes with one structured campaign:

1. inventory all PE32 vendor binaries;
2. identify WinComm register-read exports and address-width clues;
3. locate read-API name tables in vendor binaries;
4. find code xrefs to those strings;
5. correlate string xrefs with GetProcAddress call sites;
6. recover global slots that receive resolved function pointers when possible;
7. find indirect calls/loads through those slots and show their local argument setup;
8. classify each candidate as CONFIRMED_RESOLVER / STRONG / DATA_ONLY / NOT_FOUND.

The goal is to identify the real vendor-used primitive for reading 16-bit XDATA before
any further runtime SOC correlation. Proprietary binaries are read locally only and are
never copied into the public repository.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import argparse
import json
import struct
import sys

TARGET_NAMES = (
    "ReadRegEx",
    "ReadRegsEx",
    "ReadReg",
    "ReadRegs",
    "ReadMcuReg",
    "ReadMcuRegs",
    "ReadSysDevice",
    "ReadWordSysDevice",
    "NativeRead",
    "DDCCIRead",
    "I2CReadEx",
    "I2CRead",
)

PRIORITY_NAMES = (
    "ReadRegEx",
    "ReadRegsEx",
    "ReadSysDevice",
    "ReadWordSysDevice",
    "NativeRead",
    "ReadReg",
    "ReadRegs",
    "ReadMcuReg",
    "ReadMcuRegs",
)


def u16(data: bytes, off: int) -> int:
    return struct.unpack_from("<H", data, off)[0]


def u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def cstr(data: bytes, off: int, limit: int = 512) -> str:
    end = data.find(b"\0", off, min(len(data), off + limit))
    if end < 0:
        end = min(len(data), off + limit)
    return data[off:end].decode("ascii", "replace")


@dataclass
class Section:
    name: str
    va: int
    vsize: int
    raw: int
    rawsize: int
    chars: int

    @property
    def executable(self) -> bool:
        return bool(self.chars & 0x20000000)


@dataclass
class PE:
    path: Path
    data: bytes
    machine: int
    image_base: int
    sections: list[Section]
    import_rva: int
    export_rva: int

    def rva_to_off(self, rva: int) -> int | None:
        for s in self.sections:
            span = max(s.vsize, s.rawsize)
            if s.va <= rva < s.va + span:
                d = rva - s.va
                if d < s.rawsize:
                    return s.raw + d
        return None

    def off_to_rva(self, off: int) -> int | None:
        for s in self.sections:
            if s.raw <= off < s.raw + s.rawsize:
                return s.va + (off - s.raw)
        return None

    def va_to_off(self, va: int) -> int | None:
        if va < self.image_base:
            return None
        return self.rva_to_off(va - self.image_base)

    def iter_exec_ranges(self):
        for s in self.sections:
            if s.executable and s.rawsize:
                yield s, s.raw, min(len(self.data), s.raw + s.rawsize)


def parse_pe(path: Path) -> PE | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) < 0x100 or data[:2] != b"MZ":
        return None
    peoff = u32(data, 0x3C)
    if peoff + 0x108 > len(data) or data[peoff:peoff+4] != b"PE\0\0":
        return None
    machine = u16(data, peoff + 4)
    nsec = u16(data, peoff + 6)
    optsz = u16(data, peoff + 20)
    opt = peoff + 24
    if u16(data, opt) != 0x10B:
        return None
    image_base = u32(data, opt + 28)
    dd = opt + 96
    export_rva = u32(data, dd)
    import_rva = u32(data, dd + 8)
    sh = opt + optsz
    sections: list[Section] = []
    for i in range(nsec):
        o = sh + i * 40
        if o + 40 > len(data):
            break
        name = data[o:o+8].split(b"\0", 1)[0].decode("ascii", "replace")
        sections.append(Section(
            name=name,
            vsize=u32(data, o + 8),
            va=u32(data, o + 12),
            rawsize=u32(data, o + 16),
            raw=u32(data, o + 20),
            chars=u32(data, o + 36),
        ))
    return PE(path, data, machine, image_base, sections, import_rva, export_rva)


def imports(pe: PE):
    out = []
    if not pe.import_rva:
        return out
    off = pe.rva_to_off(pe.import_rva)
    if off is None:
        return out
    for idx in range(4096):
        d = off + idx * 20
        if d + 20 > len(pe.data):
            break
        oft, _ts, _fc, name_rva, ft = struct.unpack_from("<IIIII", pe.data, d)
        if not any((oft, name_rva, ft)):
            break
        noff = pe.rva_to_off(name_rva)
        dll = cstr(pe.data, noff) if noff is not None else f"rva_{name_rva:X}"
        toff = pe.rva_to_off(oft or ft)
        if toff is None:
            continue
        for j in range(8192):
            q = toff + j * 4
            if q + 4 > len(pe.data):
                break
            ent = u32(pe.data, q)
            if ent == 0:
                break
            iat_rva = ft + j * 4
            if ent & 0x80000000:
                out.append((dll, f"#{ent & 0xFFFF}", iat_rva))
                continue
            hn = pe.rva_to_off(ent)
            if hn is None or hn + 2 >= len(pe.data):
                continue
            out.append((dll, cstr(pe.data, hn + 2), iat_rva))
    return out


def exports(pe: PE):
    out = []
    if not pe.export_rva:
        return out
    off = pe.rva_to_off(pe.export_rva)
    if off is None or off + 40 > len(pe.data):
        return out
    base = u32(pe.data, off + 16)
    nfunc = u32(pe.data, off + 20)
    nname = u32(pe.data, off + 24)
    funcs_rva = u32(pe.data, off + 28)
    names_rva = u32(pe.data, off + 32)
    ords_rva = u32(pe.data, off + 36)
    funcs = pe.rva_to_off(funcs_rva)
    names = pe.rva_to_off(names_rva)
    ords = pe.rva_to_off(ords_rva)
    if None in (funcs, names, ords):
        return out
    for i in range(min(nname, 20000)):
        nrva = u32(pe.data, names + i * 4)
        noff = pe.rva_to_off(nrva)
        if noff is None:
            continue
        name = cstr(pe.data, noff)
        oi = u16(pe.data, ords + i * 2)
        if oi >= nfunc:
            continue
        frva = u32(pe.data, funcs + oi * 4)
        out.append((name, base + oi, frva))
    return out


def find_ascii(pe: PE, text: str):
    pat = text.encode("ascii") + b"\0"
    pos = 0
    while True:
        p = pe.data.find(pat, pos)
        if p < 0:
            break
        rva = pe.off_to_rva(p)
        if rva is not None:
            yield p, rva, pe.image_base + rva
        pos = p + 1


def find_all(blob: bytes, pat: bytes, start: int, end: int):
    pos = start
    while True:
        p = blob.find(pat, pos, end)
        if p < 0:
            break
        yield p
        pos = p + 1


def exec_xrefs_to_va(pe: PE, va: int):
    """Locate common x86 absolute-immediate references to a VA in executable sections."""
    imm = struct.pack("<I", va)
    hits = []
    for s, a, b in pe.iter_exec_ranges():
        # PUSH imm32
        for p in find_all(pe.data, b"\x68" + imm, a, b):
            hits.append((p, "push-imm32"))
        # MOV r32, imm32 (B8..BF)
        for op in range(0xB8, 0xC0):
            for p in find_all(pe.data, bytes([op]) + imm, a, b):
                hits.append((p, f"mov-r{op-0xB8}-imm32"))
        # PUSH dword ptr [imm32] is not a string-address xref, but LEA cannot be absolute
        # in 32-bit mode without ModRM/SIB complexity. Raw immediate fallback below.
        for p in find_all(pe.data, imm, a, b):
            if not any(abs(p-h[0]) <= 1 for h in hits):
                prev = pe.data[p-1] if p > a else None
                hits.append((p, f"raw-imm32-prev={prev:02X}" if prev is not None else "raw-imm32"))
    return sorted(set(hits))


def getproc_calls(pe: PE):
    imps = imports(pe)
    iats = [iat for dll, name, iat in imps if name == "GetProcAddress"]
    calls = []
    for iat in iats:
        va = pe.image_base + iat
        pat = b"\xFF\x15" + struct.pack("<I", va)
        for s, a, b in pe.iter_exec_ranges():
            for p in find_all(pe.data, pat, a, b):
                calls.append((p, iat, va))
    return sorted(calls)


def nearby_window(pe: PE, off: int, before=48, after=48):
    a = max(0, off - before)
    b = min(len(pe.data), off + after)
    return pe.data[a:b], a, b


def short_hex(pe: PE, center: int, before=32, after=48):
    a = max(0, center - before)
    b = min(len(pe.data), center + after)
    lines = []
    for off in range(a, b, 16):
        chunk = pe.data[off:min(off+16, b)]
        hx = " ".join(f"{x:02X}" for x in chunk)
        asc = "".join(chr(x) if 32 <= x < 127 else "." for x in chunk)
        mark = " <==" if off <= center < off + 16 else ""
        lines.append(f"{off:08X}: {hx:<47} {asc}{mark}")
    return "\n".join(lines)


def stores_after_call(pe: PE, call_off: int):
    """Best-effort stores of EAX in the first 24 bytes after a call."""
    d = pe.data
    out = []
    p = call_off + 6  # FF 15 abs32
    end = min(len(d), p + 28)
    while p < end:
        # mov [abs32],eax = A3 imm32
        if d[p:p+1] == b"\xA3" and p + 5 <= len(d):
            addr = u32(d, p+1)
            out.append((p, "mov [abs],eax", addr))
            p += 5
            continue
        # mov [abs32],eax = 89 05 imm32
        if d[p:p+2] == b"\x89\x05" and p + 6 <= len(d):
            addr = u32(d, p+2)
            out.append((p, "mov [abs],eax", addr))
            p += 6
            continue
        # mov reg,eax patterns (8B F0, 8B C8, 89 Cx)
        if p + 2 <= len(d) and d[p] in (0x8B, 0x89):
            out.append((p, "reg/local move", None))
        p += 1
    return out


def indirect_uses_of_slot(pe: PE, slot_va: int):
    imm = struct.pack("<I", slot_va)
    out = []
    patterns = [
        (b"\xFF\x15" + imm, "call [slot]"),
        (b"\xFF\x25" + imm, "jmp [slot]"),
        (b"\xA1" + imm, "mov eax,[slot]"),
        (b"\x8B\x0D" + imm, "mov ecx,[slot]"),
        (b"\x8B\x15" + imm, "mov edx,[slot]"),
        (b"\x8B\x1D" + imm, "mov ebx,[slot]"),
        (b"\x8B\x35" + imm, "mov esi,[slot]"),
        (b"\x8B\x3D" + imm, "mov edi,[slot]"),
    ]
    for s, a, b in pe.iter_exec_ranges():
        for pat, label in patterns:
            for p in find_all(pe.data, pat, a, b):
                out.append((p, label))
    return sorted(out)


def arg_setup_summary(pe: PE, call_off: int, before=40):
    """Decode only simple push forms in a local x86 window; enough for ABI clues."""
    d = pe.data
    a = max(0, call_off-before)
    out = []
    p = a
    while p < call_off:
        op = d[p]
        if op == 0x68 and p + 5 <= call_off:
            out.append((p, f"push 0x{u32(d,p+1):08X}"))
            p += 5
            continue
        if op == 0x6A and p + 2 <= call_off:
            imm = d[p+1]
            out.append((p, f"push 0x{imm:02X}"))
            p += 2
            continue
        if 0x50 <= op <= 0x57:
            out.append((p, f"push reg{op-0x50}"))
            p += 1
            continue
        if op == 0x8D and p + 3 <= call_off:
            # keep LEA as generic pointer setup marker
            out.append((p, "lea ..."))
        p += 1
    return out[-10:]


def classify_target(pe: PE, name: str, gpa_calls):
    strings = list(find_ascii(pe, name))
    if not strings:
        return {"name": name, "strings": [], "xrefs": [], "resolver_hits": [], "slots": [], "uses": [], "status": "NOT_FOUND"}
    xrefs = []
    for off, rva, va in strings:
        for xo, kind in exec_xrefs_to_va(pe, va):
            xrefs.append((off, va, xo, kind))

    resolver_hits = []
    slots = []
    uses = []
    for soff, sva, xo, kind in xrefs:
        for call_off, _iat, _gva in gpa_calls:
            # Typical resolver sequence puts string ref shortly before GetProcAddress.
            if 0 <= call_off - xo <= 96:
                resolver_hits.append((soff, sva, xo, kind, call_off))
                for st_off, st_kind, slot in stores_after_call(pe, call_off):
                    if slot is not None:
                        slots.append((slot, st_off, st_kind))
    for slot, _so, _sk in slots:
        for use_off, use_kind in indirect_uses_of_slot(pe, slot):
            uses.append((slot, use_off, use_kind, arg_setup_summary(pe, use_off)))

    if resolver_hits and uses:
        status = "CONFIRMED_RESOLVER_USED"
    elif resolver_hits:
        status = "CONFIRMED_RESOLVER"
    elif xrefs:
        status = "STRONG_CODE_XREF"
    else:
        status = "DATA_ONLY"
    return {
        "name": name,
        "strings": strings,
        "xrefs": xrefs,
        "resolver_hits": resolver_hits,
        "slots": slots,
        "uses": uses,
        "status": status,
    }


def wincomm_export_matrix(pe: PE):
    exps = {name: (ordv, rva) for name, ordv, rva in exports(pe)}
    rows = []
    for name in TARGET_NAMES:
        if name not in exps:
            continue
        ordv, rva = exps[name]
        off = pe.rva_to_off(rva)
        if off is None:
            continue
        blob = pe.data[off:off+192]
        clues = []
        if b"\x0F\xB6\x45\x08" in blob:
            clues.append("arg1-low-byte")
        if b"\x0F\xB7\x45\x08" in blob:
            clues.append("arg1-low-word")
        if b"\x8B\x75\x08" in blob or b"\x8B\x45\x08" in blob or b"\x8B\x4D\x08" in blob:
            clues.append("arg1-dword-load")
        if b"\x81\xCB\x00\xFF\x00\x00" in blob or b"\x0D\x00\xFF\x00\x00" in blob:
            clues.append("forces-FFxx")
        if b"\xC1\xEB\x08" in blob or b"\xC1\xE8\x08" in blob:
            clues.append("extracts-high-byte")
        rows.append((name, ordv, rva, off, clues))
    return rows


def choose_best(candidates):
    score_status = {
        "CONFIRMED_RESOLVER_USED": 100,
        "CONFIRMED_RESOLVER": 80,
        "STRONG_CODE_XREF": 50,
        "DATA_ONLY": 10,
        "NOT_FOUND": 0,
    }
    best = None
    best_score = -1
    for rel, results in candidates:
        for r in results:
            score = score_status.get(r["status"], 0)
            try:
                score += max(0, 20 - PRIORITY_NAMES.index(r["name"]))
            except ValueError:
                pass
            if r["name"] in {"ReadMcuReg", "ReadMcuRegs"}:
                score -= 25
            if score > best_score:
                best_score = score
                best = (rel, r, score)
    return best


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", type=Path, help="Firmware/updater root containing WinComm.dll and vendor binaries")
    ap.add_argument("--json", type=Path, help="Optional JSON report path")
    ap.add_argument("--details", action="store_true", help="Print raw local byte windows for resolver/use sites")
    args = ap.parse_args()

    root = args.root.resolve()
    if not root.is_dir():
        raise SystemExit(f"Not a directory: {root}")

    paths = sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in {".exe", ".dll"})
    pes = []
    for p in paths:
        pe = parse_pe(p)
        if pe:
            pes.append(pe)

    print("ASUS MB16AMT — consolidated SOC host-side recon campaign")
    print(f"root: {root}")
    print("OFFLINE ONLY: NO DLL LOAD; NO DEVICE I/O; NO WRITES")
    print()
    print("===== PHASE 1 — PE INVENTORY =====")
    print(f"PE32 files parsed: {len(pes)}")
    for pe in pes:
        rel = pe.path.relative_to(root)
        print(f"  {rel}  machine=0x{pe.machine:04X} base=0x{pe.image_base:08X}")
    print()

    wincomm = next((pe for pe in pes if pe.path.name.lower() == "wincomm.dll" and pe.path.parent == root), None)
    export_matrix = []
    if wincomm:
        print("===== PHASE 2 — WINCOMM READ-API ABI MATRIX =====")
        export_matrix = wincomm_export_matrix(wincomm)
        for name, ordv, rva, off, clues in export_matrix:
            tag = ", ".join(clues) if clues else "no-simple-clue"
            print(f"{name:<20} ord={ordv:>3} RVA=0x{rva:08X} file=0x{off:08X}  [{tag}]")
        print("Rule: functions forcing FFxx are MCU-register-space only; prefer full-address/high-byte-aware paths for XDATA.")
        print()
    else:
        print("===== PHASE 2 — WINCOMM READ-API ABI MATRIX =====")
        print("WinComm.dll not found at firmware root; ABI matrix skipped.")
        print()

    print("===== PHASE 3 — DYNAMIC RESOLVER / FUNCTION-POINTER ANALYSIS =====")
    candidate_reports = []
    for pe in pes:
        imps = imports(pe)
        has_gpa = any(name == "GetProcAddress" for _dll, name, _iat in imps)
        has_target_string = any(any(True for _ in find_ascii(pe, n)) for n in TARGET_NAMES)
        if not has_target_string:
            continue
        rel = str(pe.path.relative_to(root))
        gpa = getproc_calls(pe) if has_gpa else []
        results = [classify_target(pe, n, gpa) for n in TARGET_NAMES]
        interesting = [r for r in results if r["status"] != "NOT_FOUND"]
        candidate_reports.append((rel, interesting))
        print(f"-- {rel} --")
        print(f"GetProcAddress import={'yes' if has_gpa else 'no'} decoded IAT-calls={len(gpa)}")
        for r in interesting:
            print(
                f"  {r['name']:<20} {r['status']:<24} "
                f"strings={len(r['strings'])} xrefs={len(r['xrefs'])} "
                f"resolver_hits={len(r['resolver_hits'])} slots={len(r['slots'])} uses={len(r['uses'])}"
            )
            for slot, use_off, use_kind, pushes in r["uses"][:8]:
                setup = "; ".join(text for _p, text in pushes) or "no simple PUSH clues"
                print(f"      use file+0x{use_off:08X} {use_kind} slot=0x{slot:08X}  args: {setup}")
                if args.details:
                    print(short_hex(pe, use_off, 48, 48))
            if args.details:
                for _soff, _sva, xo, _kind, call_off in r["resolver_hits"][:4]:
                    print(f"      resolver xref file+0x{xo:08X} -> GetProcAddress call file+0x{call_off:08X}")
                    print(short_hex(pe, call_off, 64, 48))
        print()

    print("===== PHASE 4 — CROSS-CANDIDATE VERDICT =====")
    best = choose_best(candidate_reports)
    if best:
        rel, r, score = best
        print(f"BEST HOST-SIDE READ CANDIDATE: {rel} :: {r['name']}  status={r['status']} score={score}")
        if r["status"] == "CONFIRMED_RESOLVER_USED":
            print("CONFIRMED: vendor code resolves this API dynamically and later uses the recovered function-pointer slot.")
            print("Next runtime step should reproduce ONLY the observed vendor call convention/initialization for this candidate.")
        elif r["status"] == "CONFIRMED_RESOLVER":
            print("CONFIRMED resolver, but no indirect use was recovered with the simple x86 patterns yet.")
            print("Next static step is to expand slot-use decoding around this exact resolver; do not probe random APIs.")
        elif r["status"] == "STRONG_CODE_XREF":
            print("Code references the API name, but no GetProcAddress association was proven yet.")
        else:
            print("Only data presence is proven; do not treat this as a callable vendor path yet.")
    else:
        print("No read API candidate found in vendor code.")
    print()

    print("===== PHASE 5 — KNOWN SOC DEAD-END GUARDRAILS =====")
    print("ELIMINATED: ReadMcuReg for D8xx XDATA (WinComm forces register-space addressing / prior runtime calls invalid).")
    print("ELIMINATED: 1:F7B2 / D833 as dynamic SOC source on its proven caller path (R7 receives constant 1).")
    print("DO NOT REPEAT: broad VCP sweep, D9FF/ED charge-policy tracing, DA86 timer path, generic numeric-renderer hunting.")
    print("TARGET REMAINS: establish one valid read primitive -> correlate live 0..100 SOC -> trace matching XDATA variable statically.")
    print()

    print("===== CAMPAIGN SUMMARY =====")
    status_counts = {}
    for _rel, results in candidate_reports:
        for r in results:
            status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1
    for k in sorted(status_counts):
        print(f"{k}: {status_counts[k]}")
    print(f"vendor PE candidates analyzed: {len(candidate_reports)}")
    if best:
        print(f"NEXT_TARGET={best[0]}::{best[1]['name']}::{best[1]['status']}")

    if args.json:
        report = {
            "root": str(root),
            "pe_count": len(pes),
            "wincomm_export_matrix": [
                {"name": n, "ordinal": o, "rva": rva, "file_offset": off, "clues": clues}
                for n, o, rva, off, clues in export_matrix
            ],
            "candidates": [
                {"file": rel, "results": results}
                for rel, results in candidate_reports
            ],
            "best": None if not best else {"file": best[0], "result": best[1], "score": best[2]},
            "status_counts": status_counts,
        }
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(f"JSON_REPORT={args.json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

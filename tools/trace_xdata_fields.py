"""Trace selected XDATA fields in the verified ASUS MB16AMT V020 image.

Read-only/offline. This helper inventories decoded `MOV DPTR,#addr` references
for chosen XDATA fields and prints instruction-coherent local contexts. It also
tracks simple adjacent `INC DPTR` sequences so fields reached from a structure
base (for example DCC5 from DCC4) are not missed.

This is evidence collection, not automatic semantic naming.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib

from analyze_banked_abi import BANK_SIZE, LENGTHS, SHA, inventory, traverse, word
from mcs51 import decode


def parse_addr(text: str) -> int:
    text = text.strip().lower().removeprefix("0x")
    return int(text, 16)


def local_listing(data: bytes, bank: int, decoded, center: int, before: int = 0x30, after: int = 0x50):
    starts = sorted(pc for (b, pc) in decoded if b == bank and max(0, center-before) <= pc < min(BANK_SIZE, center+after))
    chunk = data[bank*BANK_SIZE:(bank+1)*BANK_SIZE]
    lines = []
    for pc in starts:
        try:
            text = decode(chunk, pc)
        except Exception as e:
            text = f"<decode error {e}>"
        mark = " >>>" if pc == center else ""
        lines.append(f"{bank}:{pc:04X}  {text}{mark}")
    return "\n".join(lines)


def classify_simple_accesses(data: bytes, decoded, bank: int, start_pc: int, targets: set[int], max_insn: int = 16):
    """Follow only straight-line DPTR evolution from a decoded MOV DPTR,#imm16.

    Calls, jumps, conditional branches, returns, and a second MOV DPTR stop the
    local proof. This intentionally under-approximates rather than guessing.
    """
    chunk = data[bank*BANK_SIZE:(bank+1)*BANK_SIZE]
    pc = start_pc
    if chunk[pc] != 0x90:
        return []
    dptr = word(chunk, pc+1)
    out = []
    for _ in range(max_insn):
        if (bank, pc) not in decoded:
            break
        op = chunk[pc]
        size = LENGTHS[op]
        if op == 0x90:
            if pc != start_pc:
                break
            dptr = word(chunk, pc+1)
        elif op == 0xA3:
            dptr = (dptr + 1) & 0xFFFF
        elif op == 0xE0:
            if dptr in targets:
                out.append((pc, dptr, "READ", "MOVX A,@DPTR"))
        elif op == 0xF0:
            if dptr in targets:
                out.append((pc, dptr, "WRITE", "MOVX @DPTR,A"))
        elif op in (0x02, 0x12, 0x22, 0x32, 0x73, 0x40, 0x50, 0x60, 0x70, 0x80, 0x10, 0x20, 0x30, 0xD5) or 0xB4 <= op <= 0xBF or 0xD8 <= op <= 0xDF or op & 0x1F in (0x01, 0x11):
            break
        pc += size
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("firmware", type=Path)
    ap.add_argument("--addresses", nargs="+", default=["DCC4", "DCC5", "DA69", "DA6C"],
                    help="hex XDATA addresses (default: DCC4 DCC5 DA69 DA6C)")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    data = args.firmware.read_bytes()
    if len(data) != 0xE0000 or hashlib.sha256(data).hexdigest() != SHA:
        raise SystemExit("Refusing an image other than verified ASUS V020")

    targets = {parse_addr(x) for x in args.addresses}
    thunks = inventory(data)
    decoded, *_ = traverse(data, thunks)
    args.out.mkdir(parents=True, exist_ok=True)

    report = []
    emit = lambda s="": report.append(str(s))
    emit("ASUS MB16AMT V020 — focused XDATA field provenance")
    emit(f"SHA256: {SHA}")
    emit("READ-ONLY OFFLINE ANALYSIS; NO DEVICE I/O")
    emit("Targets: " + " ".join(f"{a:04X}" for a in sorted(targets)))

    # Direct DPTR loads to the target or up to 8 bytes before it, allowing
    # adjacent structure members reached through INC DPTR to be classified.
    candidates = []
    for (bank, pc), size in sorted(decoded.items()):
        p = bank * BANK_SIZE + pc
        if data[p] != 0x90:
            continue
        base = word(data, p+1)
        if any(0 <= t-base <= 8 for t in targets):
            accesses = classify_simple_accesses(data, decoded, bank, pc, targets)
            if accesses or base in targets:
                candidates.append((bank, pc, base, accesses))

    emit()
    emit(f"Candidate decoded DPTR bases: {len(candidates)}")
    totals = {t: {"READ": 0, "WRITE": 0, "BASE_ONLY": 0} for t in targets}

    for bank, pc, base, accesses in candidates:
        emit()
        emit(f"===== {bank}:{pc:04X} MOV DPTR,#{base:04X} =====")
        if accesses:
            for apc, addr, kind, text in accesses:
                totals[addr][kind] += 1
                emit(f"ACCESS {kind:5s} {addr:04X} at {bank}:{apc:04X} ({text})")
        else:
            if base in targets:
                totals[base]["BASE_ONLY"] += 1
                emit(f"BASE_ONLY {base:04X}: no straight-line MOVX proof before control-flow boundary")
        emit(local_listing(data, bank, decoded, pc))

    emit()
    emit("===== SUMMARY =====")
    for t in sorted(targets):
        c = totals[t]
        emit(f"{t:04X}: read={c['READ']} write={c['WRITE']} base_only={c['BASE_ONLY']}")
    emit()
    emit("Limit: computed/generic pointers and paths crossing calls are intentionally not inferred.")

    out = args.out / "xdata-field-trace.txt"
    out.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Report written: {out}")
    for t in sorted(targets):
        c = totals[t]
        print(f"{t:04X}: read={c['READ']} write={c['WRITE']} base_only={c['BASE_ONLY']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Focused static trace for the strongest VCP 0xED candidate in ASUS V020.

Read-only/offline. The generic VCP scan found one decoded `MOV R7,#0xED` at
physical bank 9:F1C0. This tool prints instruction-coherent slices around that
site and the immediately-called routines, inventories decoded callers, and
extracts direct XDATA references in those slices. It does not assert that the
site is the DDC handler; the output is evidence for manual data-flow review.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib
import json

from analyze_banked_abi import BANK_SIZE, LENGTHS, SHA, inventory, traverse, word
from mcs51 import listing

# Candidate and immediate call chain seen in the first heuristic pass.
REGIONS = [
    (9, 0xF160, 0xF1E0, "ED candidate context"),
    (9, 0xFD20, 0xFDA0, "callee 9:FD52 context"),
    (9, 0xA8E0, 0xA980, "callee 9:A940 context"),
    (8, 0xE780, 0xE860, "far callee 8:E7E4 context"),
]
TARGETS = [(9, 0xF1C0), (9, 0xFD52), (9, 0xA940), (8, 0xE7E4)]


def decoded_callers(data, decoded, thunks, target_bank, target_pc):
    rows = []
    # Direct same-bank calls/jumps.
    for (bank, pc), size in sorted(decoded.items()):
        p = bank * BANK_SIZE + pc
        op = data[p]
        if bank == target_bank and op in (0x02, 0x12) and word(data, p + 1) == target_pc:
            rows.append((bank, pc, "LJMP" if op == 0x02 else "LCALL", None))
        # Calls/jumps through common bank thunk.
        if op in (0x02, 0x12):
            t = word(data, p + 1)
            if t in thunks and thunks[t] == (target_bank, target_pc):
                rows.append((bank, pc, "LJMP-thunk" if op == 0x02 else "LCALL-thunk", t))
    return rows


def xdata_refs(data, decoded, bank, lo, hi):
    out = []
    for pc in range(lo, hi):
        if (bank, pc) not in decoded:
            continue
        p = bank * BANK_SIZE + pc
        if data[p] == 0x90 and pc + 2 < BANK_SIZE:  # MOV DPTR,#imm16
            addr = word(data, p + 1)
            # Keep XDATA-ish addresses and bank-control range; omit code pointers.
            if addr >= 0x8000:
                nxt = pc + 3
                nextop = data[bank * BANK_SIZE + nxt] if nxt < BANK_SIZE else None
                out.append((pc, addr, nextop))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("firmware", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    data = args.firmware.read_bytes()
    if len(data) != 0xE0000 or hashlib.sha256(data).hexdigest() != SHA:
        raise SystemExit("Refusing an image other than verified ASUS V020")

    thunks = inventory(data)
    decoded, edges, indirect, reserved, overlaps = traverse(data, thunks)
    args.out.mkdir(parents=True, exist_ok=True)

    report = []
    def emit(s=""):
        report.append(str(s))

    emit("ASUS MB16AMT V020 — focused VCP ED candidate trace")
    emit(f"SHA256: {SHA}")
    emit("READ-ONLY OFFLINE ANALYSIS; NO DEVICE I/O")
    emit()
    emit("Interpretation rule: 9:F1C0 is only a candidate until surrounding data-flow proves DDC/VCP semantics.")

    for bank, lo, hi, title in REGIONS:
        emit()
        emit(f"===== {title}: {bank}:{lo:04X}-{hi:04X} =====")
        try:
            emit(listing(data, bank, lo, hi, thunks))
        except Exception as e:
            emit(f"<listing failed: {e}>")

        refs = xdata_refs(data, decoded, bank, lo, hi)
        emit("-- direct MOV DPTR,#XDATA-like references --")
        if not refs:
            emit("(none at decoded boundaries)")
        for pc, addr, nextop in refs:
            emit(f"{bank}:{pc:04X} -> {addr:04X}; next opcode {nextop:02X}" if nextop is not None else f"{bank}:{pc:04X} -> {addr:04X}")

    emit()
    emit("===== DECODED CALLERS OF TARGETS =====")
    caller_summary = {}
    for bank, pc in TARGETS:
        rows = decoded_callers(data, decoded, thunks, bank, pc)
        key = f"{bank}:{pc:04X}"
        caller_summary[key] = []
        emit(f"-- {key}: {len(rows)} decoded callers --")
        for cb, cp, kind, thunk in rows:
            if thunk is None:
                text = f"{cb}:{cp:04X} {kind} -> {key}"
            else:
                text = f"{cb}:{cp:04X} {kind} {thunk:04X} -> {key}"
            caller_summary[key].append(text)
            emit(text)

    # Inventory the exact immediate ED site and its following decoded instructions.
    emit()
    emit("===== CANDIDATE ASSERTIONS =====")
    base = 9 * BANK_SIZE
    assert data[base + 0xF1C0:base + 0xF1C2] == bytes.fromhex("7F ED"), "9:F1C0 is no longer MOV R7,#ED"
    emit("9:F1C0 bytes 7F ED = MOV R7,#ED (confirmed exact bytes)")
    emit("Do not infer preservation of R7 across 9:FD52 or 9:A940 without the listing/data-flow.")

    summary = {
        "sha256": SHA,
        "candidate": "9:F1C0 MOV R7,#ED",
        "targets": [f"{b}:{p:04X}" for b, p in TARGETS],
        "decoded_callers": caller_summary,
        "status": "candidate trace only; manual data-flow confirmation required",
        "safety": "offline read-only; no device I/O",
    }
    (args.out / "vcp-ed-focused-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (args.out / "vcp-ed-focused-trace.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

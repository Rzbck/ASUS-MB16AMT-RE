"""Trace provenance of the D833 OSD parameter in verified ASUS MB16AMT V020.

Read-only/offline. The previous 99/100 guard analysis showed that D833 is copied
from a caller-provided value and then used by generic OSD formatting branches.
This tool therefore traces who writes D833 and who calls the candidate entry
around 1:F7B2, with local provenance for R7/R5 before the call.

It does NOT assume D833 is SOC. The goal is to find a caller that feeds it from a
0..100 battery-state source.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib

from analyze_banked_abi import BANK_SIZE, LENGTHS, SHA, inventory, traverse, word
from mcs51 import decode

TARGET_XDATA = 0xD833
TARGET_BANK = 1
TARGET_ENTRY = 0xF7B2

CONTROL_OPS = {0x02, 0x12, 0x22, 0x32, 0x73, 0x40, 0x50, 0x60, 0x70, 0x80, 0x10, 0x20, 0x30, 0xD5}


def starts_for_bank(decoded, bank: int) -> list[int]:
    return sorted(pc for b, pc in decoded if b == bank)


def fmt(data: bytes, bank: int, pc: int, thunks) -> str:
    chunk = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    text = decode(chunk, pc)
    if chunk[pc] in (0x02, 0x12):
        t = word(chunk, pc + 1)
        if t in thunks:
            tb, tp = thunks[t]
            text += f" ; -> {tb}:{tp:04X}"
    return text


def local_context(data: bytes, decoded, thunks, bank: int, center: int, before: int = 0x50, after: int = 0x70):
    out = []
    for pc in starts_for_bank(decoded, bank):
        if max(0, center - before) <= pc < min(0x10000, center + after):
            mark = " <<<" if pc == center else ""
            out.append(f"{bank}:{pc:04X}  {fmt(data, bank, pc, thunks)}{mark}")
    return out


def direct_target(chunk: bytes, pc: int):
    op = chunk[pc]
    if op in (0x02, 0x12):
        return word(chunk, pc + 1)
    if op & 0x1F in (0x01, 0x11):  # AJMP/ACALL
        n = LENGTHS[op]
        return ((pc + n) & 0xF800) | ((op & 0xE0) << 3) | chunk[pc + 1]
    return None


def classify_d833_access(data: bytes, decoded_set, bank: int, pc: int):
    """Straight-line classify access following MOV DPTR,#D833."""
    chunk = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    if chunk[pc] != 0x90 or word(chunk, pc + 1) != TARGET_XDATA:
        return []
    out = []
    cur = pc
    dptr = TARGET_XDATA
    for _ in range(10):
        if (bank, cur) not in decoded_set:
            break
        op = chunk[cur]
        if op == 0x90 and cur != pc:
            break
        if op == 0xA3:
            dptr = (dptr + 1) & 0xFFFF
        elif op == 0xE0:
            out.append((cur, dptr, "READ"))
        elif op == 0xF0:
            out.append((cur, dptr, "WRITE"))
        elif op in CONTROL_OPS or 0xB4 <= op <= 0xBF or 0xD8 <= op <= 0xDF or op & 0x1F in (0x01, 0x11):
            break
        cur += LENGTHS[op]
    return out


def trace_reg_before(data: bytes, decoded, bank: int, call_pc: int, reg: int, limit: int = 24) -> str:
    """Best-effort local backward provenance for R0..R7 before a call site."""
    starts = starts_for_bank(decoded, bank)
    prev = [pc for pc in starts if pc < call_pc]
    chunk = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    # Walk backwards but stop at strong control boundaries.
    for pc in reversed(prev[-limit:]):
        op = chunk[pc]
        # MOV Rn,#imm
        if op == 0x78 + reg:
            return f"R{reg} <- immediate 0x{chunk[pc+1]:02X} at {bank}:{pc:04X}"
        # MOV Rn,direct
        if op == 0xA8 + reg:
            return f"R{reg} <- direct {chunk[pc+1]:02X}h at {bank}:{pc:04X}"
        # MOV Rn,A
        if op == 0xF8 + reg:
            # inspect immediately preceding producer of A
            idx = starts.index(pc)
            prior = starts[max(0, idx - 8):idx]
            for q in reversed(prior):
                qop = chunk[q]
                if qop == 0xE0:
                    # find nearest preceding MOV DPTR,#imm
                    qidx = starts.index(q)
                    for r in reversed(starts[max(0, qidx - 6):qidx]):
                        if chunk[r] == 0x90:
                            return f"R{reg} <- A <- XDATA {word(chunk,r+1):04X} via {bank}:{q:04X} (DPTR at {r:04X})"
                        if chunk[r] in CONTROL_OPS:
                            break
                    return f"R{reg} <- A <- MOVX at {bank}:{q:04X}; DPTR provenance unresolved"
                if qop == 0x74:
                    return f"R{reg} <- A <- immediate 0x{chunk[q+1]:02X} at {bank}:{q:04X}"
                if 0xE8 <= qop <= 0xEF:
                    return f"R{reg} <- A <- R{qop & 7} at {bank}:{q:04X}"
                if qop in CONTROL_OPS or 0xB4 <= qop <= 0xBF or 0xD8 <= qop <= 0xDF:
                    break
            return f"R{reg} <- A at {bank}:{pc:04X}; A provenance unresolved locally"
        # A call/jump can clobber register provenance; stop rather than guess.
        if op in (0x02, 0x12, 0x22, 0x32) or op & 0x1F in (0x01, 0x11):
            break
    return f"R{reg} provenance unresolved in local caller window"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("firmware", type=Path)
    args = ap.parse_args()

    data = args.firmware.read_bytes()
    if len(data) != 0xE0000 or hashlib.sha256(data).hexdigest() != SHA:
        raise SystemExit("Refusing an image other than verified ASUS V020")

    thunks = inventory(data)
    decoded, *_ = traverse(data, thunks)
    decoded_set = set(decoded)

    print("ASUS MB16AMT V020 — D833 SOC provenance trace")
    print(f"SHA256: {SHA}")
    print("READ-ONLY OFFLINE ANALYSIS; NO DEVICE I/O")
    print("Scope: upstream source of the 0..100-like OSD parameter; charge-policy path excluded")
    print()

    refs = []
    writes = []
    for bank in range(14):
        chunk = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
        for pc in starts_for_bank(decoded, bank):
            if chunk[pc] == 0x90 and word(chunk, pc + 1) == TARGET_XDATA:
                accesses = classify_d833_access(data, decoded_set, bank, pc)
                refs.append((bank, pc, accesses))
                if any(kind == "WRITE" and addr == TARGET_XDATA for _, addr, kind in accesses):
                    writes.append((bank, pc, accesses))

    print("===== ALL DECODED D833 BASE REFERENCES =====")
    print(f"total={len(refs)} writers={len(writes)}")
    for bank, pc, accesses in refs:
        desc = ", ".join(f"{kind}@{apc:04X}:{addr:04X}" for apc, addr, kind in accesses) or "base-only"
        print(f"{bank}:{pc:04X}  {desc}")
    print()

    print("===== DIRECT D833 WRITERS =====")
    if not writes:
        print("(none decoded)")
    for bank, pc, accesses in writes:
        print()
        print(f"-- writer base {bank}:{pc:04X} --")
        for line in local_context(data, decoded, thunks, bank, pc):
            print(line)
    print()

    print(f"===== EXACT CALL/JUMP SITES TO CANDIDATE ENTRY {TARGET_BANK}:{TARGET_ENTRY:04X} =====")
    callers = []
    chunk = data[TARGET_BANK * BANK_SIZE:(TARGET_BANK + 1) * BANK_SIZE]
    for pc in starts_for_bank(decoded, TARGET_BANK):
        t = direct_target(chunk, pc)
        if t == TARGET_ENTRY:
            callers.append(pc)
    if not callers:
        print("(none decoded; entry may be reached by fallthrough/indirect control flow)")
    for pc in callers:
        print()
        print(f"-- caller {TARGET_BANK}:{pc:04X} -> {TARGET_ENTRY:04X} --")
        print("R7 provenance: " + trace_reg_before(data, decoded, TARGET_BANK, pc, 7))
        print("R5 provenance: " + trace_reg_before(data, decoded, TARGET_BANK, pc, 5))
        for line in local_context(data, decoded, thunks, TARGET_BANK, pc, before=0x70, after=0x30):
            print(line)
    print()

    print("===== ENTRY 1:F7B2 CONTEXT =====")
    for line in local_context(data, decoded, thunks, TARGET_BANK, TARGET_ENTRY, before=0x20, after=0x80):
        print(line)
    print()

    print("===== INTERPRETATION RULE =====")
    print("Promote a SOC source only if caller provenance shows the value passed into D833 comes from a battery-state variable or acquisition path and stays in 0..100 semantics.")
    print("If D833 is fed by many unrelated callers/values, treat it as generic OSD state and move upstream from the caller that specifically renders the battery item.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

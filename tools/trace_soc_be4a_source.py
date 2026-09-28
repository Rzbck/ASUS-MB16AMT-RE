"""Trace the exact value source feeding the 1:F7B2 OSD formatter in ASUS MB16AMT V020.

Read-only/offline. Previous analysis proved the only decoded banked caller of
1:F7B2 is 10:B07D, and that R7 is assigned from A immediately after
10:B073 LCALL BE4A; INC A. This tool therefore focuses only on 10:BE4A and
its return value. It does not scan charge-policy state or assume BE4A is SOC.
"""
from __future__ import annotations

from pathlib import Path
from collections import deque
import argparse
import hashlib

from analyze_banked_abi import BANK_SIZE, LENGTHS, SHA, inventory, traverse, word
from mcs51 import decode

BANK = 10
ENTRY = 0xBE4A
BRIDGE_CALL = 0xB073
BRIDGE_FORMAT = 0xB07D


def starts_for_bank(decoded, bank: int) -> list[int]:
    return sorted(pc for b, pc in decoded if b == bank)


def fmt(data: bytes, bank: int, pc: int, thunks) -> str:
    chunk = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    text = decode(chunk, pc)
    op = chunk[pc]
    if op in (0x02, 0x12):
        t = word(chunk, pc + 1)
        if t in thunks:
            tb, tp = thunks[t]
            text += f" ; thunk {t:04X} -> {tb}:{tp:04X}"
    return text


def aj_target(chunk: bytes, pc: int) -> int:
    op = chunk[pc]
    n = LENGTHS[op]
    nxt = (pc + n) & 0xFFFF
    return (nxt & 0xF800) | ((op & 0xE0) << 3) | chunk[pc + 1]


def rel_target(chunk: bytes, pc: int) -> int:
    op = chunk[pc]
    n = LENGTHS[op]
    nxt = (pc + n) & 0xFFFF
    rel = chunk[pc + n - 1]
    if rel >= 128:
        rel -= 256
    return (nxt + rel) & 0xFFFF


def function_cfg(data: bytes, decoded, thunks, bank: int, entry: int, node_limit: int = 512):
    """Conservative same-bank CFG for one routine; calls are recorded, not followed."""
    decoded_set = set(decoded)
    chunk = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    q = deque([entry])
    seen = set()
    calls = []
    indirect = []
    rets = []

    while q and len(seen) < node_limit:
        pc = q.popleft()
        if (bank, pc) not in decoded_set or pc in seen:
            continue
        seen.add(pc)
        op = chunk[pc]
        n = LENGTHS[op]
        nxt = (pc + n) & 0xFFFF

        if op in (0x22, 0x32):
            rets.append(pc)
            continue
        if op == 0x73:
            indirect.append(pc)
            continue

        # LJMP / LCALL
        if op in (0x02, 0x12):
            t = word(chunk, pc + 1)
            resolved = thunks.get(t)
            if op == 0x12:
                calls.append((pc, t, resolved))
                q.append(nxt)
            else:
                if resolved is None:
                    q.append(t)
                else:
                    # A banked LJMP leaves this routine; record like a call edge.
                    calls.append((pc, t, resolved))
            continue

        # AJMP / ACALL
        if op & 0x1F in (0x01, 0x11):
            t = aj_target(chunk, pc)
            if op & 0x1F == 0x11:
                calls.append((pc, t, thunks.get(t)))
                q.append(nxt)
            else:
                q.append(t)
            continue

        # Conditional branches and SJMP.
        if op in (0x10, 0x20, 0x30, 0x40, 0x50, 0x60, 0x70, 0x80, 0xD5) or 0xB4 <= op <= 0xBF or 0xD8 <= op <= 0xDF:
            q.append(rel_target(chunk, pc))
            if op != 0x80:
                q.append(nxt)
            continue

        q.append(nxt)

    return sorted(seen), calls, sorted(indirect), sorted(rets)


def xdata_refs(data: bytes, pcs: list[int], bank: int):
    """Report immediate DPTR XDATA bases and nearby MOVX access direction."""
    chunk = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    pcset = set(pcs)
    out = []
    for pc in pcs:
        if chunk[pc] != 0x90:
            continue
        addr = word(chunk, pc + 1)
        cur = pc + 3
        dptr = addr
        acts = []
        for _ in range(8):
            if cur not in pcset:
                break
            op = chunk[cur]
            if op == 0x90:
                break
            if op == 0xA3:
                dptr = (dptr + 1) & 0xFFFF
            elif op == 0xE0:
                acts.append((cur, dptr, "READ"))
            elif op == 0xF0:
                acts.append((cur, dptr, "WRITE"))
            if op in (0x02, 0x12, 0x22, 0x32, 0x73, 0x80) or 0xB4 <= op <= 0xBF:
                break
            cur += LENGTHS[op]
        out.append((pc, addr, acts))
    return out


def direct_callers(data: bytes, decoded, thunks, target_bank: int, target_pc: int):
    callers = []
    for bank in range(14):
        chunk = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
        for b, pc in decoded:
            if b != bank:
                continue
            op = chunk[pc]
            if op not in (0x02, 0x12):
                continue
            t = word(chunk, pc + 1)
            if t in thunks:
                db, dp = thunks[t]
                if (db, dp) == (target_bank, target_pc):
                    callers.append((bank, pc, t, "thunk"))
            elif bank == target_bank and t == target_pc:
                callers.append((bank, pc, t, "direct"))
    return sorted(callers)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("firmware", type=Path)
    args = ap.parse_args()

    data = args.firmware.read_bytes()
    if len(data) != 0xE0000 or hashlib.sha256(data).hexdigest() != SHA:
        raise SystemExit("Refusing an image other than verified ASUS V020")

    thunks = inventory(data)
    decoded, *_ = traverse(data, thunks)
    pcs, calls, indirect, rets = function_cfg(data, decoded, thunks, BANK, ENTRY)

    print("ASUS MB16AMT V020 — focused 10:BE4A return-value trace")
    print(f"SHA256: {SHA}")
    print("READ-ONLY OFFLINE ANALYSIS; NO DEVICE I/O")
    print("Scope: source of A returned by 10:BE4A, which becomes R7 for 1:F7B2")
    print()

    print("===== PROVEN CALLER BRIDGE =====")
    for pc in range(0xB065, 0xB081):
        if (BANK, pc) in decoded:
            mark = " <<< BE4A" if pc == BRIDGE_CALL else (" <<< F7B2" if pc == BRIDGE_FORMAT else "")
            print(f"{BANK}:{pc:04X}  {fmt(data, BANK, pc, thunks)}{mark}")
    print("Interpretation: BE4A return A -> INC A -> MOVX @DPTR,A -> MOV R7,A -> F7B2")
    print()

    print("===== ALL DECODED CALLERS OF 10:BE4A =====")
    callers = direct_callers(data, decoded, thunks, BANK, ENTRY)
    if not callers:
        print("(none decoded)")
    for bank, pc, raw, kind in callers:
        print(f"{bank}:{pc:04X}  {fmt(data, bank, pc, thunks)} [{kind}]")
    print()

    print("===== REACHABLE CFG FROM 10:BE4A =====")
    print(f"instructions={len(pcs)} rets={len(rets)} indirect_jumps={len(indirect)} calls={len(calls)}")
    for pc in pcs:
        print(f"{BANK}:{pc:04X}  {fmt(data, BANK, pc, thunks)}")
    print()

    print("===== XDATA REFERENCES INSIDE BE4A CFG =====")
    refs = xdata_refs(data, pcs, BANK)
    if not refs:
        print("(none)")
    for pc, addr, acts in refs:
        if acts:
            detail = ", ".join(f"{kind}@{apc:04X}:{a:04X}" for apc, a, kind in acts)
        else:
            detail = "base-only / access beyond local straight-line window"
        print(f"{BANK}:{pc:04X} -> {addr:04X}  {detail}")
    print()

    print("===== CALLEES FROM BE4A CFG =====")
    if not calls:
        print("(none)")
    for pc, raw, resolved in calls:
        if resolved:
            print(f"{BANK}:{pc:04X} -> thunk {raw:04X} -> {resolved[0]}:{resolved[1]:04X}")
        else:
            print(f"{BANK}:{pc:04X} -> {BANK}:{raw:04X}")
    print()

    print("===== RETURN SITES =====")
    if not rets:
        print("(none decoded)")
    starts = starts_for_bank(decoded, BANK)
    chunk = data[BANK * BANK_SIZE:(BANK + 1) * BANK_SIZE]
    for ret in rets:
        print(f"-- RET {BANK}:{ret:04X} --")
        prior = [pc for pc in starts if pc <= ret][-18:]
        for pc in prior:
            print(f"{BANK}:{pc:04X}  {fmt(data, BANK, pc, thunks)}")
    print()

    print("===== INTERPRETATION RULE =====")
    print("If BE4A returns a value read from a stable battery-state XDATA/acquisition path and the +1 yields 0..100 semantics, promote it as a SOC source candidate.")
    print("If BE4A instead returns an index/counter/menu state, reject the F7B2 branch as SOC and stop following it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

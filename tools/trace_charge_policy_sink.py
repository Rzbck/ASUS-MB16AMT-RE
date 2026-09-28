"""Trace the immediate sink of the confirmed VCP-ED charge-policy result.

Read-only/offline. Proven chain before this tool:
  Set-VCP ED -> D9FF.bit7 -> policy evaluator 9:E703 -> status in R7
  9:E7F2 LCALL E703
  9:E7F5 LCALL thunk 162E -> 13:3DE6

This tracer focuses on 13:3DE6, shows how it consumes R7, its XDATA state,
and its direct outgoing calls. It also expands each direct callee one level so
hardware-facing Type-C / PMIC / charger paths can be recognized without another
global scan.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib

from analyze_banked_abi import BANK_SIZE, LENGTHS, SHA, inventory, traverse, word
from mcs51 import decode

SINK_BANK = 13
SINK = 0x3DE6
SINK_LO = 0x3DA0
SINK_HI = 0x3F40


def starts(decoded, bank, lo, hi):
    return sorted(pc for b, pc in decoded if b == bank and lo <= pc < hi)


def instr(data, bank, pc):
    chunk = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    return decode(chunk, pc)


def signed8(v):
    return v - 0x100 if v & 0x80 else v


def direct_target(data, bank, pc):
    chunk = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    op = chunk[pc]
    n = LENGTHS[op]
    nxt = (pc + n) & 0xFFFF
    if op in (0x02, 0x12):
        return word(chunk, pc + 1)
    if op & 0x1F in (0x01, 0x11):
        return (nxt & 0xF800) | ((op & 0xE0) << 3) | chunk[pc + 1]
    if op in {0x10,0x20,0x30,0x40,0x50,0x60,0x70,0x80,0xD5,0xD8,0xD9,0xDA,0xDB,0xDC,0xDD,0xDE,0xDF} or 0xB4 <= op <= 0xBF:
        return (nxt + signed8(chunk[pc + n - 1])) & 0xFFFF
    return None


def resolved_target(data, thunks, bank, pc):
    chunk = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    op = chunk[pc]
    t = direct_target(data, bank, pc)
    if t is None:
        return None
    if op in (0x02, 0x12) or op & 0x1F in (0x01, 0x11):
        return thunks.get(t, (bank, t))
    return bank, t


def transfer_kind(data, bank, pc):
    op = data[bank * BANK_SIZE + pc]
    if op == 0x12 or op & 0x1F == 0x11:
        return "LCALL"
    if op == 0x02 or op & 0x1F == 0x01:
        return "LJMP"
    return "BR"


def print_region(data, decoded, thunks, bank, lo, hi):
    for pc in starts(decoded, bank, lo, hi):
        text = instr(data, bank, pc)
        t = resolved_target(data, thunks, bank, pc)
        if t:
            text += f" ; {transfer_kind(data, bank, pc)} -> {t[0]}:{t[1]:04X}"
        print(f"{bank}:{pc:04X}  {text}")


def dptr_refs(data, decoded, bank, lo, hi):
    chunk = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    for pc in starts(decoded, bank, lo, hi):
        if chunk[pc] == 0x90:
            yield pc, word(chunk, pc + 1)


def direct_outgoing(data, decoded, thunks, bank, lo, hi):
    seen = set()
    for pc in starts(decoded, bank, lo, hi):
        op = data[bank * BANK_SIZE + pc]
        if not (op in (0x02,0x12) or op & 0x1F in (0x01,0x11)):
            continue
        t = resolved_target(data, thunks, bank, pc)
        if t and not (t[0] == bank and lo <= t[1] < hi):
            row = (pc, transfer_kind(data, bank, pc), t[0], t[1])
            if row not in seen:
                seen.add(row)
                yield row


def incoming(data, decoded, thunks, tb, tp):
    rows = []
    for b, pc in sorted(decoded):
        t = resolved_target(data, thunks, b, pc)
        if t == (tb, tp):
            rows.append((b, pc, instr(data, b, pc)))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("firmware", type=Path)
    args = ap.parse_args()

    data = args.firmware.read_bytes()
    if len(data) != 0xE0000 or hashlib.sha256(data).hexdigest() != SHA:
        raise SystemExit("Refusing an image other than verified ASUS V020")

    thunks = inventory(data)
    decoded, *_ = traverse(data, thunks)
    decoded = set(decoded)

    print("ASUS MB16AMT V020 — charge-policy sink trace")
    print(f"SHA256: {SHA}")
    print("READ-ONLY OFFLINE ANALYSIS; NO DEVICE I/O")
    print()

    print("===== PROVEN BRIDGE INTO SINK =====")
    print("9:E7F2 LCALL E703  ; policy result returned in R7")
    print("9:E7F5 LCALL 162E  ; thunk -> 13:3DE6, with no R7 overwrite between calls")
    print("=> 13:3DE6 is the immediate sink of the policy status")
    print()

    print("===== INCOMING CALLS TO 13:3DE6 =====")
    rows = incoming(data, decoded, thunks, SINK_BANK, SINK)
    if rows:
        for b, pc, text in rows:
            print(f"{b}:{pc:04X}  {text}")
    else:
        print("(none decoded)")
    print()

    print("===== SINK REGION 13:3DE6 =====")
    print_region(data, decoded, thunks, SINK_BANK, SINK_LO, SINK_HI)
    print()

    print("===== XDATA REFERENCES IN SINK REGION =====")
    refs = list(dptr_refs(data, decoded, SINK_BANK, SINK_LO, SINK_HI))
    if refs:
        for pc, addr in refs:
            tag = " hardware-ish" if (addr >= 0xF000 or 0xB000 <= addr < 0xC000) else ""
            print(f"13:{pc:04X} -> {addr:04X}{tag}")
    else:
        print("(none)")
    print()

    outs = list(direct_outgoing(data, decoded, thunks, SINK_BANK, SINK_LO, SINK_HI))
    print("===== DIRECT OUTGOING CALLS/JUMPS =====")
    if outs:
        for pc, kind, b, target in outs:
            print(f"13:{pc:04X} {kind} -> {b}:{target:04X}")
    else:
        print("(none)")
    print()

    print("===== ONE-HOP CALLEE NEIGHBORHOODS =====")
    seen = set()
    for _, kind, b, target in outs:
        if kind != "LCALL" or (b, target) in seen:
            continue
        seen.add((b, target))
        print(f"-- callee {b}:{target:04X} --")
        lo = max(0, target - 0x18)
        hi = min(0x10000, target + 0x60)
        print_region(data, decoded, thunks, b, lo, hi)
        refs2 = list(dptr_refs(data, decoded, b, lo, hi))
        if refs2:
            print("  XDATA:")
            for pc, addr in refs2:
                tag = " hardware-ish" if (addr >= 0xF000 or 0xB000 <= addr < 0xC000) else ""
                print(f"  {b}:{pc:04X} -> {addr:04X}{tag}")
        print()

    print("===== INTERPRETATION RULE =====")
    print("Promote 13:3DE6 to a hardware bridge only if its R7-dependent path reaches")
    print("independently identified Type-C/PMIC/charger I/O or hardware-facing helpers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

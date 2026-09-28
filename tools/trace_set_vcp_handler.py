"""Trace the confirmed ASUS V020 Set-VCP handler around bank9:9452.

Read-only/offline. This tracer starts from the statically proven DDCCI command
branch at bank9:EC5B where command 0x03 routes to 9:9452, then inventories the
handler's direct XDATA references, opcode comparisons, calls, branches, and the
common helper at 0:210D. It deliberately does not assign semantics to vendor VCP
codes until their provenance from D993 (RxBuf source opcode) is explicit.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib

from analyze_banked_abi import BANK_SIZE, LENGTHS, SHA, inventory, traverse, word
from mcs51 import decode

BANK = 9
START = 0x9452
END = 0x9CA3

RX_FIELDS = {
    0xD992: "RxBuf[2] command",
    0xD993: "RxBuf[3] VCP/source opcode",
    0xD994: "RxBuf[4] value-hi?",
    0xD995: "RxBuf[5] value-lo?",
    0xD996: "RxBuf[6]",
    0xD997: "RxBuf[7]",
}

VENDORISH = {
    0xAA, 0xAC, 0xAE, 0xB2, 0xB6, 0xC6, 0xC8, 0xCC,
    0xD6, 0xDC, 0xDF, 0xE0, 0xE3, 0xE4, 0xE9, 0xEB,
    0xED, 0xF0, 0xF1, 0xFD, 0xFF,
}


def fmt_call(data, thunks, bank, pc):
    p = bank * BANK_SIZE + pc
    op = data[p]
    if op not in (0x02, 0x12):
        return None
    t = word(data, p + 1)
    kind = "LJMP" if op == 0x02 else "LCALL"
    if t in thunks:
        b, a = thunks[t]
        return f"{kind} {t:04X} -> {b}:{a:04X}"
    return f"{kind} {bank}:{t:04X}"


def instr(data, bank, pc):
    chunk = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    return decode(chunk, pc)


def region_starts(decoded, bank, lo, hi):
    return sorted(pc for b, pc in decoded if b == bank and lo <= pc < hi)


def direct_dptr_refs(data, decoded, bank, lo, hi):
    out = []
    chunk = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    for pc in region_starts(decoded, bank, lo, hi):
        if chunk[pc] != 0x90:
            continue
        addr = word(chunk, pc + 1)
        nxt = pc + 3
        nxt_text = instr(data, bank, nxt) if (bank, nxt) in decoded else ""
        out.append((pc, addr, nxt_text))
    return out


def branch_target(chunk, pc):
    op = chunk[pc]
    size = LENGTHS[op]
    nxt = (pc + size) & 0xFFFF

    # SJMP and conditional rel8 branches.
    rel_ops = {
        0x10, 0x20, 0x30, 0x40, 0x50, 0x60, 0x70, 0x80,
        0xD5, 0xD8, 0xD9, 0xDA, 0xDB, 0xDC, 0xDD, 0xDE, 0xDF,
    }
    if op in rel_ops or 0xB4 <= op <= 0xBF:
        rel = chunk[pc + size - 1]
        if rel >= 0x80:
            rel -= 0x100
        return (nxt + rel) & 0xFFFF

    if op in (0x02, 0x12):
        return word(chunk, pc + 1)

    if op & 0x1F in (0x01, 0x11):
        return (nxt & 0xF800) | ((op & 0xE0) << 3) | chunk[pc + 1]

    return None


def compact_listing(data, decoded, thunks, bank, lo, hi):
    chunk = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    rows = []
    for pc in region_starts(decoded, bank, lo, hi):
        text = instr(data, bank, pc)
        extra = fmt_call(data, thunks, bank, pc)
        if extra:
            text += f" ; {extra}"
        rows.append(f"{bank}:{pc:04X}  {text}")
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("firmware", type=Path)
    ap.add_argument("--full", action="store_true", help="also print the complete 9:9452-9CA2 decoded region")
    args = ap.parse_args()

    data = args.firmware.read_bytes()
    if len(data) != 0xE0000 or hashlib.sha256(data).hexdigest() != SHA:
        raise SystemExit("Refusing an image other than verified ASUS V020")

    thunks = inventory(data)
    decoded, edges, indirect, reserved, overlaps = traverse(data, thunks)
    decoded = set(decoded)
    chunk = data[BANK * BANK_SIZE:(BANK + 1) * BANK_SIZE]

    print("ASUS MB16AMT V020 — confirmed Set-VCP handler trace")
    print(f"SHA256: {SHA}")
    print("READ-ONLY OFFLINE ANALYSIS; NO DEVICE I/O")
    print()

    print("===== CONFIRMED COMMAND DISPATCH LINK =====")
    for pc in region_starts(decoded, 9, 0xEC5B, 0xEC8B):
        print(f"9:{pc:04X}  {instr(data, 9, pc)}")
    print("Interpretation: D992==0x03 takes branch EC78 and calls 9:9452.")
    print()

    print("===== SET-VCP ENTRY 9:9452 =====")
    for pc in region_starts(decoded, 9, 0x9452, 0x9485):
        text = instr(data, 9, pc)
        extra = fmt_call(data, thunks, 9, pc)
        if extra:
            text += f" ; {extra}"
        print(f"9:{pc:04X}  {text}")
    print()

    print("===== DIRECT RX BUFFER REFERENCES INSIDE 9:9452-9CA2 =====")
    refs = direct_dptr_refs(data, decoded, BANK, START, END)
    for pc, addr, nxt in refs:
        if addr in RX_FIELDS:
            print(f"9:{pc:04X} -> {addr:04X} ({RX_FIELDS[addr]}); next={nxt}")
    print()

    print("===== DIRECT D993 OPCODE USES IN SET-VCP REGION =====")
    d993_sites = [(pc, nxt) for pc, addr, nxt in refs if addr == 0xD993]
    if not d993_sites:
        print("(none)")
    for pc, nxt in d993_sites:
        print(f"-- 9:{pc:04X} --")
        for q in region_starts(decoded, BANK, max(START, pc - 0x10), min(END, pc + 0x28)):
            text = instr(data, BANK, q)
            extra = fmt_call(data, thunks, BANK, q)
            if extra:
                text += f" ; {extra}"
            print(f"9:{q:04X}  {text}")
    print()

    print("===== IMMEDIATE COMPARES / NORMALIZATIONS IN SET-VCP REGION =====")
    interesting = []
    for pc in region_starts(decoded, BANK, START, END):
        p = BANK * BANK_SIZE + pc
        op = data[p]
        txt = instr(data, BANK, pc)
        imm = None
        if op in (0x24, 0x34, 0x44, 0x54, 0x64, 0x74, 0x94, 0xB4):
            imm = data[p + 1]
        elif 0xB8 <= op <= 0xBF:
            imm = data[p + 1]
        if imm is not None:
            if imm in VENDORISH or op in (0xB4, 0x94) or 0xB8 <= op <= 0xBF:
                interesting.append((pc, imm, txt))
    for pc, imm, txt in interesting:
        mark = " <== ED" if imm == 0xED else ""
        print(f"9:{pc:04X} imm={imm:02X}  {txt}{mark}")
    print()

    print("===== CALL/JUMP TARGETS FROM SET-VCP REGION =====")
    seen = set()
    for pc in region_starts(decoded, BANK, START, END):
        c = fmt_call(data, thunks, BANK, pc)
        if c and (pc, c) not in seen:
            seen.add((pc, c))
            print(f"9:{pc:04X}  {c}")
    print()

    print("===== DIRECT XDATA WRITES/READS OF POWER-LIKE DAxx STATE =====")
    for pc, addr, nxt in refs:
        if 0xDA00 <= addr <= 0xDAFF:
            print(f"9:{pc:04X} -> {addr:04X}; next={nxt}")
    print()

    print("===== COMMON HELPER 0:210D NEIGHBORHOOD =====")
    for pc in region_starts(decoded, 0, 0x20E0, 0x2140):
        text = instr(data, 0, pc)
        extra = fmt_call(data, thunks, 0, pc)
        if extra:
            text += f" ; {extra}"
        print(f"0:{pc:04X}  {text}")
    print()

    print("===== RAW/DECODED ED LITERALS INSIDE CONFIRMED SET-VCP REGION =====")
    ed_hits = []
    for pc in region_starts(decoded, BANK, START, END):
        p = BANK * BANK_SIZE + pc
        op = data[p]
        size = LENGTHS[op]
        bs = data[p:p+size]
        if 0xED in bs[1:]:
            ed_hits.append(pc)
            print(f"9:{pc:04X}  {instr(data, BANK, pc)}  bytes={' '.join(f'{x:02X}' for x in bs)}")
    if not ed_hits:
        print("No immediate/data byte ED appears in decoded instructions of 9:9452-9CA2.")
    print()

    print("===== NEXT INTERPRETATION RULE =====")
    print("Promote an ED handler only if control/data flow from D993 reaches that branch/value.")
    print("If ED is absent as an immediate, recover the switch/table transform fed by D993 rather than scanning literals.")

    if args.full:
        print()
        print("===== FULL DECODED REGION 9:9452-9CA2 =====")
        for line in compact_listing(data, decoded, thunks, BANK, START, END):
            print(line)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

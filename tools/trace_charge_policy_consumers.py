"""Trace consumers of the confirmed VCP-ED charge-policy bit D9FF.bit7.

Read-only/offline. The ED Set-VCP handler proves that D9FF.bit7 is the active-high
internal policy state corresponding to "Charging From NB/PC". This tool does not
re-discover ED. It finds direct bit7 consumers and then expands the most promising
control-flow regions so getters/UI paths can be separated from power-policy logic.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib

from analyze_banked_abi import BANK_SIZE, LENGTHS, SHA, inventory, traverse, word
from mcs51 import decode

D9FF = 0xD9FF

FOCUS = [
    (9, 0xE6F0, 0xE750, "policy block around 9:E70D"),
    (9, 0xEBC0, 0xEC40, "policy block around 9:EBE1/EC06"),
    (9, 0xCFB0, 0xD080, "consumer around 9:CFC3"),
    (10, 0xBE90, 0xBF10, "state conversion around 10:BEC8"),
]

HELPERS = [0xA902, 0xA929, 0xA944, 0xA994, 0xA995, 0xAA1F, 0xAA28, 0xAA2A, 0xAA2E]


def instr(data, bank, pc):
    chunk = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    return decode(chunk, pc)


def starts(decoded, bank, lo, hi):
    return sorted(pc for b, pc in decoded if b == bank and lo <= pc < hi)


def signed8(v):
    return v - 0x100 if v & 0x80 else v


def direct_target(chunk, pc):
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
    t = direct_target(chunk, pc)
    if t is None:
        return None
    if op in (0x02, 0x12) or op & 0x1F in (0x01, 0x11):
        if t in thunks:
            return thunks[t]
        return bank, t
    return bank, t


def fmt_transfer(data, thunks, bank, pc):
    chunk = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    op = chunk[pc]
    t = resolved_target(data, thunks, bank, pc)
    if t is None:
        return None
    kind = (
        "LCALL" if op == 0x12 or op & 0x1F == 0x11 else
        "LJMP" if op == 0x02 or op & 0x1F == 0x01 else
        "BR"
    )
    return kind, t


def dptr_refs(data, decoded, bank, lo, hi):
    chunk = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    out = []
    for pc in starts(decoded, bank, lo, hi):
        if chunk[pc] == 0x90:
            out.append((pc, word(chunk, pc + 1)))
    return out


def print_region(data, decoded, thunks, bank, lo, hi):
    for pc in starts(decoded, bank, lo, hi):
        text = instr(data, bank, pc)
        tr = fmt_transfer(data, thunks, bank, pc)
        if tr:
            text += f" ; {tr[0]} -> {tr[1][0]}:{tr[1][1]:04X}"
        print(f"{bank}:{pc:04X}  {text}")


def incoming_to_range(data, decoded, thunks, bank, lo, hi):
    rows = []
    for sb, sp in sorted(decoded):
        t = resolved_target(data, thunks, sb, sp)
        if not t:
            continue
        if t[0] == bank and lo <= t[1] < hi and not (sb == bank and lo <= sp < hi):
            rows.append((sb, sp, t[1], instr(data, sb, sp)))
    return rows


def outgoing_from_range(data, decoded, thunks, bank, lo, hi):
    rows = []
    for pc in starts(decoded, bank, lo, hi):
        tr = fmt_transfer(data, thunks, bank, pc)
        if tr and tr[0] in ("LCALL", "LJMP"):
            tb, tp = tr[1]
            if not (tb == bank and lo <= tp < hi):
                rows.append((pc, tr[0], tb, tp))
    return rows


def bit7_sites(data, decoded):
    rows = []
    for bank in range(14):
        chunk = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
        pcs = starts(decoded, bank, 0, 0x10000)
        pos = {pc:i for i,pc in enumerate(pcs)}
        for pc in pcs:
            if chunk[pc] != 0x90 or word(chunk, pc + 1) != D9FF:
                continue
            i = pos[pc]
            window = pcs[i+1:i+10]
            saw_movx = False
            for q in window:
                op = chunk[q]
                if op == 0xE0:
                    saw_movx = True
                if saw_movx and op == 0x54 and chunk[q+1] == 0x80:
                    rows.append((bank, pc, q))
                    break
                if op in (0x22, 0x02, 0x80):
                    break
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

    print("ASUS MB16AMT V020 — confirmed charge-policy consumer trace")
    print(f"SHA256: {SHA}")
    print("READ-ONLY OFFLINE ANALYSIS; NO DEVICE I/O")
    print()
    print("===== FIXED PROVENANCE =====")
    print("Set-VCP ED -> 9:9C7A")
    print("ED=0 -> D9FF.bit7=1; ED!=0 -> D9FF.bit7=0")
    print("Live behavior: ED=0 Charging From NB/PC; ED=1 No Charging From NB/PC")
    print()

    print("===== DIRECT D9FF.bit7 CONSUMERS =====")
    for bank, dptr_pc, mask_pc in bit7_sites(data, decoded):
        print(f"{bank}:{dptr_pc:04X} -> bit7 mask at {bank}:{mask_pc:04X}")
    print()

    print("===== BIT-EXTRACTION HELPER NEIGHBORHOODS (BANK 9) =====")
    seen = set()
    for h in HELPERS:
        lo, hi = max(0, h-8), min(0x10000, h+12)
        key=(lo,hi)
        if key in seen: continue
        seen.add(key)
        print(f"-- helper around 9:{h:04X} --")
        print_region(data, decoded, thunks, 9, lo, hi)
    print()

    for bank, lo, hi, label in FOCUS:
        print(f"===== {label.upper()} =====")
        print("-- incoming transfers --")
        incoming = incoming_to_range(data, decoded, thunks, bank, lo, hi)
        if incoming:
            for sb,sp,tp,text in incoming:
                print(f"{sb}:{sp:04X} -> {bank}:{tp:04X}  {text}")
        else:
            print("(none decoded)")
        print("-- region --")
        print_region(data, decoded, thunks, bank, lo, hi)
        print("-- XDATA refs --")
        for pc, addr in dptr_refs(data, decoded, bank, lo, hi):
            print(f"{bank}:{pc:04X} -> {addr:04X}")
        print("-- outgoing calls/jumps --")
        outs = outgoing_from_range(data, decoded, thunks, bank, lo, hi)
        if outs:
            for pc,kind,tb,tp in outs:
                print(f"{bank}:{pc:04X} {kind} -> {tb}:{tp:04X}")
        else:
            print("(none)")
        print()

    print("===== INTERPRETATION RULE =====")
    print("Getter/UI candidates may read bit7 but only normalize/store it locally.")
    print("Prioritize a block only when bit7 gates calls or XDATA that lead toward Type-C/PMIC/power state.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

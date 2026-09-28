"""Trace exact VCP ED charge-policy state into firmware consumers.

Read-only/offline. Prints directly to stdout.

Starting point is already proven:
  D992==03 -> Set-VCP 9:9452
  D993==ED -> handler 9:9C7A
  ED=0 sets D9FF.bit7, ED!=0 clears it; both clear D9FF.bit4.

This tool inventories every decoded MOV DPTR,#D9FF / #DA69 site across all
logical banks, prints compact surrounding listings, and shows the exact tail of
9:9C7A so the next power-management hop can be identified without another broad
scan.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib

from analyze_banked_abi import BANK_SIZE, SHA, inventory, traverse, word
from mcs51 import decode

TARGETS = (0xD9FF, 0xDA69)


def instr(data, bank, pc):
    chunk = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    return decode(chunk, pc)


def starts(decoded, bank, lo=0, hi=0x10000):
    return sorted(pc for b, pc in decoded if b == bank and lo <= pc < hi)


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


def listing(data, decoded, thunks, bank, lo, hi, mark=None):
    for pc in starts(decoded, bank, lo, hi):
        text = instr(data, bank, pc)
        extra = fmt_call(data, thunks, bank, pc)
        if extra:
            text += f" ; {extra}"
        suffix = "  >>>" if pc == mark else ""
        print(f"{bank}:{pc:04X}  {text}{suffix}")


def dptr_sites(data, decoded, addr):
    out = []
    for bank in range(14):
        chunk = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
        for pc in starts(decoded, bank):
            if chunk[pc] == 0x90 and word(chunk, pc + 1) == addr:
                out.append((bank, pc))
    return out


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

    print("ASUS MB16AMT V020 — exact ED charge-state trace")
    print(f"SHA256: {SHA}")
    print("READ-ONLY OFFLINE ANALYSIS; NO DEVICE I/O")
    print()

    print("===== EXACT ED HANDLER + CONTINUATION =====")
    listing(data, decoded, thunks, 9, 0x9C7A, 0x9CA6)
    print()

    print("===== PROVEN ED BIT SEMANTICS =====")
    print("ED=0  -> D9FF.bit7=1")
    print("ED!=0 -> D9FF.bit7=0")
    print("both  -> D9FF.bit4=0")
    print("live experiment: ED=0 Charging From NB/PC; ED=1 No Charging From NB/PC")
    print("=> D9FF.bit7 is strong-evidence active-high 'charge from NB/PC allowed' policy state")
    print()

    for addr in TARGETS:
        sites = dptr_sites(data, decoded, addr)
        print(f"===== ALL DECODED MOV DPTR,#{addr:04X} SITES ({len(sites)}) =====")
        for bank, pc in sites:
            print(f"\n-- {bank}:{pc:04X} --")
            listing(data, decoded, thunks, bank, max(0, pc - 0x18), min(0x10000, pc + 0x30), mark=pc)
        print()

    print("===== NEXT INTERPRETATION RULE =====")
    print("Prioritize D9FF consumers that explicitly test bit7 or preserve/mask 0x80,")
    print("then follow their calls/XDATA into USB-C / power-management state.")
    print("Treat DA69 as generic dirty/update state unless its downstream path proves power semantics.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

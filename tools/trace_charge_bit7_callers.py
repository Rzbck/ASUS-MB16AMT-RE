"""Trace all logical consumers of the confirmed D9FF.bit7 charge-policy state.

Read-only/offline. VCP ED is already proven to update D9FF.bit7. This tool avoids
following known display-only sink 13:3DE6 and instead inventories every decoded
caller of the bank9 bit7 helpers:

- 9:AA2A loads D9FF and falls through to the bit7 extractor.
- 9:AA2E is the generic bit7 extractor for a value already in A.

For AA2E callers the surrounding window is printed so provenance from D9FF can be
checked explicitly. Direct D9FF/ANL #80 sites are also listed for completeness.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib

from analyze_banked_abi import BANK_SIZE, LENGTHS, SHA, inventory, traverse, word
from mcs51 import decode

D9FF = 0xD9FF
TARGETS = {(9, 0xAA2A): "AA2A load-D9FF+bit7 helper", (9, 0xAA2E): "AA2E generic bit7 helper"}


def starts(decoded, bank, lo=0, hi=0x10000):
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
    if op in (0x02,0x12) or op & 0x1F in (0x01,0x11):
        if t in thunks:
            return thunks[t]
        return bank, t
    return bank, t


def print_window(data, decoded, thunks, bank, center, before=0x28, after=0x48):
    lo = max(0, center - before)
    hi = min(0x10000, center + after)
    chunk = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    for pc in starts(decoded, bank, lo, hi):
        text = decode(chunk, pc)
        mark = " <<<" if pc == center else ""
        t = resolved_target(data, thunks, bank, pc)
        if t is not None:
            op = chunk[pc]
            if op in (0x02,0x12) or op & 0x1F in (0x01,0x11):
                text += f" ; -> {t[0]}:{t[1]:04X}"
        print(f"{bank}:{pc:04X}  {text}{mark}")


def dptr_refs(data, decoded, bank, center, radius=0x60):
    chunk = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    rows=[]
    for pc in starts(decoded, bank, max(0,center-radius), min(0x10000,center+radius)):
        if chunk[pc] == 0x90:
            rows.append((pc, word(chunk, pc+1)))
    return rows


def direct_bit7_sites(data, decoded):
    rows=[]
    for bank in range(14):
        chunk=data[bank*BANK_SIZE:(bank+1)*BANK_SIZE]
        pcs=starts(decoded,bank)
        pos={pc:i for i,pc in enumerate(pcs)}
        for pc in pcs:
            if chunk[pc] != 0x90 or word(chunk,pc+1) != D9FF:
                continue
            i=pos[pc]
            saw_read=False
            for q in pcs[i+1:i+12]:
                op=chunk[q]
                if op==0xE0:
                    saw_read=True
                if saw_read and op==0x54 and chunk[q+1]==0x80:
                    rows.append((bank,pc,q))
                    break
                if op in (0x22,0x02,0x80):
                    break
    return rows


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("firmware", type=Path)
    args=ap.parse_args()

    data=args.firmware.read_bytes()
    if len(data)!=0xE0000 or hashlib.sha256(data).hexdigest()!=SHA:
        raise SystemExit("Refusing an image other than verified ASUS V020")

    thunks=inventory(data)
    decoded,*_=traverse(data,thunks)
    decoded=set(decoded)

    print("ASUS MB16AMT V020 — exhaustive charge-bit7 helper caller trace")
    print(f"SHA256: {SHA}")
    print("READ-ONLY OFFLINE ANALYSIS; NO DEVICE I/O")
    print()
    print("===== FIXED PROVENANCE =====")
    print("Set-VCP ED -> D9FF.bit7 (active-high charge-from-NB/PC allowed)")
    print("13:3DE6 path is display/scaler configuration, not promoted as power hardware")
    print()

    print("===== DIRECT D9FF + ANL #80 SITES =====")
    for b,dp,mask in direct_bit7_sites(data,decoded):
        print(f"{b}:{dp:04X} -> mask at {b}:{mask:04X}")
    print()

    callers=[]
    for b,pc in sorted(decoded):
        t=resolved_target(data,thunks,b,pc)
        if t in TARGETS:
            callers.append((b,pc,t))

    print("===== ALL DECODED CALLERS OF BIT7 HELPERS =====")
    for t,label in TARGETS.items():
        subset=[x for x in callers if x[2]==t]
        print(f"-- {label} {t[0]}:{t[1]:04X}; callers={len(subset)} --")
        if not subset:
            print("(none)")
        for b,pc,_ in subset:
            print(f"{b}:{pc:04X}  {decode(data[b*BANK_SIZE:(b+1)*BANK_SIZE],pc)}")
    print()

    print("===== CALLER CONTEXTS =====")
    for b,pc,t in callers:
        print(f"-- caller {b}:{pc:04X} -> {TARGETS[t]} --")
        print_window(data,decoded,thunks,b,pc)
        refs=dptr_refs(data,decoded,b,pc)
        if refs:
            print("  XDATA refs in local window:")
            for rp,addr in refs:
                print(f"  {b}:{rp:04X} -> {addr:04X}")
        print()

    print("===== INTERPRETATION RULE =====")
    print("AA2A callers are direct logical consumers of D9FF.bit7.")
    print("AA2E callers are only charge-bit consumers when local provenance shows A came from D9FF.")
    print("Prioritize contexts that leave display/scaler registers and enter Type-C/PMIC/charger-facing code.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Trace indirect/banked references to logical 1:F7B2 in verified MB16AMT V020.

Read-only/offline. D833 is generic OSD state; this tool does NOT treat it as SOC.
It answers one narrow question: who reaches the 1:F7B2 OSD formatter that accepts
R7/R5 and applies the <100 branch?

It checks the known Realtek bank-thunk ABI first, then decoded direct edges, then
raw pointer-like byte references only as lower-confidence evidence.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib

from analyze_banked_abi import BANK_SIZE, LENGTHS, SHA, inventory, traverse, word
from mcs51 import decode

TARGET_BANK = 1
TARGET_PC = 0xF7B2
CONTROL_OPS = {0x02,0x12,0x22,0x32,0x73,0x40,0x50,0x60,0x70,0x80,0x10,0x20,0x30,0xD5}


def starts_for_bank(decoded, bank):
    return sorted(pc for b, pc in decoded if b == bank)


def direct_target(chunk: bytes, pc: int):
    op = chunk[pc]
    if op in (0x02, 0x12):
        return word(chunk, pc + 1)
    if op & 0x1F in (0x01, 0x11):
        n = LENGTHS[op]
        return ((pc + n) & 0xF800) | ((op & 0xE0) << 3) | chunk[pc + 1]
    return None


def fmt(data, bank, pc, thunks):
    chunk = data[bank*BANK_SIZE:(bank+1)*BANK_SIZE]
    text = decode(chunk, pc)
    t = direct_target(chunk, pc)
    if t in thunks:
        db, dp = thunks[t]
        text += f" ; thunk {t:04X} -> {db}:{dp:04X}"
    return text


def trace_reg_before(data, decoded, bank, call_pc, reg, limit=36):
    starts = starts_for_bank(decoded, bank)
    pos = {pc:i for i,pc in enumerate(starts)}
    prev = [pc for pc in starts if pc < call_pc]
    chunk = data[bank*BANK_SIZE:(bank+1)*BANK_SIZE]
    for pc in reversed(prev[-limit:]):
        op = chunk[pc]
        if op == 0x78 + reg:
            return f"R{reg} <- immediate 0x{chunk[pc+1]:02X} at {bank}:{pc:04X}"
        if op == 0xA8 + reg:
            return f"R{reg} <- direct {chunk[pc+1]:02X}h at {bank}:{pc:04X}"
        if op == 0xF8 + reg:
            idx = pos[pc]
            for q in reversed(starts[max(0,idx-10):idx]):
                qop = chunk[q]
                if qop == 0xE0:
                    qidx = pos[q]
                    for r in reversed(starts[max(0,qidx-8):qidx]):
                        if chunk[r] == 0x90:
                            return f"R{reg} <- A <- XDATA {word(chunk,r+1):04X} via {bank}:{q:04X} (DPTR {r:04X})"
                        if chunk[r] in CONTROL_OPS or 0xB4 <= chunk[r] <= 0xBF or 0xD8 <= chunk[r] <= 0xDF:
                            break
                    return f"R{reg} <- A <- MOVX at {bank}:{q:04X}; DPTR unresolved"
                if qop == 0x74:
                    return f"R{reg} <- A <- immediate 0x{chunk[q+1]:02X} at {bank}:{q:04X}"
                if 0xE8 <= qop <= 0xEF:
                    return f"R{reg} <- A <- R{qop & 7} at {bank}:{q:04X}"
                if qop in CONTROL_OPS or 0xB4 <= qop <= 0xBF or 0xD8 <= qop <= 0xDF:
                    break
            return f"R{reg} <- A at {bank}:{pc:04X}; A unresolved locally"
        if op in (0x02,0x12,0x22,0x32) or op & 0x1F in (0x01,0x11):
            break
    return f"R{reg} provenance unresolved locally"


def context(data, decoded, thunks, bank, center, before=0x50, after=0x20):
    lo, hi = max(0,center-before), min(0x10000,center+after)
    for pc in starts_for_bank(decoded, bank):
        if lo <= pc < hi:
            mark = " <<<" if pc == center else ""
            print(f"{bank}:{pc:04X}  {fmt(data,bank,pc,thunks)}{mark}")


def raw_hits(chunk: bytes, pat: bytes):
    out=[]; p=chunk.find(pat)
    while p >= 0:
        out.append(p); p=chunk.find(pat,p+1)
    return out


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("firmware", type=Path)
    args=ap.parse_args()
    data=args.firmware.read_bytes()
    if len(data)!=0xE0000 or hashlib.sha256(data).hexdigest()!=SHA:
        raise SystemExit("Refusing an image other than verified ASUS V020")

    thunks=inventory(data)
    decoded, edges, indirect, *_ = traverse(data, thunks)

    print("ASUS MB16AMT V020 — indirect SOC OSD caller trace")
    print(f"SHA256: {SHA}")
    print("READ-ONLY OFFLINE ANALYSIS; NO DEVICE I/O")
    print("Target: logical 1:F7B2 only; D833 remains generic OSD state")
    print()

    target_thunks=sorted(t for t,dst in thunks.items() if dst==(TARGET_BANK,TARGET_PC))
    print("===== BANK-THUNK TARGETS FOR 1:F7B2 =====")
    if target_thunks:
        for t in target_thunks: print(f"thunk {t:04X} -> 1:F7B2")
    else:
        print("(none in canonical 741-thunk ABI)")
    print()

    incoming=[e for e in edges if e[4]==TARGET_BANK and e[5]==TARGET_PC]
    print("===== DECODED BANKED EDGES TO 1:F7B2 =====")
    if not incoming:
        print("(none)")
    for bank,pc,kind,abi_target,db,dp in incoming:
        print(f"{bank}:{pc:04X} {kind} {abi_target:04X} -> {db}:{dp:04X}")
        print("  R7: "+trace_reg_before(data,decoded,bank,pc,7))
        print("  R5: "+trace_reg_before(data,decoded,bank,pc,5))
        context(data,decoded,thunks,bank,pc)
        print()

    print("===== SAME-BANK DIRECT CONTROL REFERENCES TO ADDRESS F7B2 =====")
    direct=[]
    for bank in range(14):
        chunk=data[bank*BANK_SIZE:(bank+1)*BANK_SIZE]
        for pc in starts_for_bank(decoded,bank):
            if direct_target(chunk,pc)==TARGET_PC:
                direct.append((bank,pc))
                print(f"{bank}:{pc:04X}  {fmt(data,bank,pc,thunks)}")
    if not direct: print("(none)")
    print()

    print("===== RAW POINTER-LIKE REFERENCES =====")
    patterns=[("BE16",bytes.fromhex("F7 B2")),("LE16",bytes.fromhex("B2 F7")),("bank+BE",bytes.fromhex("01 F7 B2")),("BE+bank",bytes.fromhex("F7 B2 01"))]
    total=0
    for name,pat in patterns:
        rows=[]
        for bank in range(14):
            chunk=data[bank*BANK_SIZE:(bank+1)*BANK_SIZE]
            for pc in raw_hits(chunk,pat): rows.append((bank,pc))
        print(f"{name} {pat.hex(' ').upper()}: {len(rows)}")
        for bank,pc in rows[:40]:
            chunk=data[bank*BANK_SIZE:(bank+1)*BANK_SIZE]
            lo=max(0,pc-8); hi=min(BANK_SIZE,pc+len(pat)+10)
            print(f"  {bank}:{pc:04X}  {chunk[lo:hi].hex(' ').upper()}")
        if len(rows)>40: print(f"  ... {len(rows)-40} more")
        total += len(rows)
    print()

    print("===== NEARBY INDIRECT-JUMP SITES IN BANK 1 =====")
    near=[pc for b,pc in indirect if b==1 and abs(pc-TARGET_PC)<=0x800]
    if near:
        for pc in near: print(f"1:{pc:04X}  {fmt(data,1,pc,thunks)}")
    else:
        print("(none within +/-0x800)")
    print()

    print("===== INTERPRETATION RULE =====")
    print("Promote only a caller/selector that demonstrably feeds the 1:F7B2 formatter with a battery-state 0..100 value.")
    print("Raw byte hits are locator evidence only; they are not calls unless structure/control flow proves it.")
    return 0

if __name__=="__main__":
    raise SystemExit(main())

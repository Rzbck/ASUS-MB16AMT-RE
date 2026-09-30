"""Trace callers/consumers of the confirmed D9FF.bit7 charge-policy gates.

Read-only/offline. The previous stage proved Set-VCP ED controls D9FF.bit7 and
identified 9:E703 and 9:EBE1 as real policy evaluators that extract bit7 from the
D9FF state and return a small status code (notably 0 or 6). This tool follows the
call chain around those evaluators and prints the enclosing caller regions so the
returned status can be tied to downstream power/Type-C behavior.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib
import json

from analyze_banked_abi import BANK_SIZE, LENGTHS, SHA, inventory, traverse, word
from mcs51 import decode

TARGETS = [(9,0xE703),(9,0xEBE1),(9,0xE759),(9,0xE7F2)]
REGIONS = [
    (9,0xE730,0xE830,"bridge around E759/E7F2"),
    (9,0xEBC0,0xEC50,"EBE1 policy evaluator"),
]


def instr(data,bank,pc):
    chunk=data[bank*BANK_SIZE:(bank+1)*BANK_SIZE]
    return decode(chunk,pc)


def starts(decoded,bank,lo,hi):
    return sorted(pc for b,pc in decoded if b==bank and lo<=pc<hi)


def signed8(v): return v-0x100 if v&0x80 else v


def direct_target(chunk,pc):
    op=chunk[pc]; n=LENGTHS[op]; nxt=(pc+n)&0xFFFF
    if op in (0x02,0x12): return word(chunk,pc+1)
    if op&0x1F in (0x01,0x11): return (nxt&0xF800)|((op&0xE0)<<3)|chunk[pc+1]
    if op in {0x10,0x20,0x30,0x40,0x50,0x60,0x70,0x80,0xD5,0xD8,0xD9,0xDA,0xDB,0xDC,0xDD,0xDE,0xDF} or 0xB4<=op<=0xBF:
        return (nxt+signed8(chunk[pc+n-1]))&0xFFFF
    return None


def resolved_target(data,thunks,bank,pc):
    chunk=data[bank*BANK_SIZE:(bank+1)*BANK_SIZE]; op=chunk[pc]; t=direct_target(chunk,pc)
    if t is None: return None
    if op in (0x02,0x12) or op&0x1F in (0x01,0x11):
        return thunks.get(t,(bank,t))
    return bank,t


def kind(data,bank,pc):
    op=data[bank*BANK_SIZE+pc]
    if op==0x12 or op&0x1F==0x11: return "LCALL"
    if op==0x02 or op&0x1F==0x01: return "LJMP"
    return "BR"


def print_region(data,decoded,thunks,bank,lo,hi):
    for pc in starts(decoded,bank,lo,hi):
        text=instr(data,bank,pc)
        t=resolved_target(data,thunks,bank,pc)
        if t:
            text += f" ; {kind(data,bank,pc)} -> {t[0]}:{t[1]:04X}"
        print(f"{bank}:{pc:04X}  {text}")


def incoming_exact(data,decoded,thunks,target):
    out=[]
    for b,pc in sorted(decoded):
        t=resolved_target(data,thunks,b,pc)
        if t==target:
            out.append((b,pc,instr(data,b,pc)))
    return out


def dptr_refs(data,decoded,bank,lo,hi):
    chunk=data[bank*BANK_SIZE:(bank+1)*BANK_SIZE]
    for pc in starts(decoded,bank,lo,hi):
        if chunk[pc]==0x90:
            yield pc,word(chunk,pc+1)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("firmware",type=Path)
    ap.add_argument("--summary",type=Path,help="Write compact decoded-edge evidence, without firmware bytes")
    args=ap.parse_args()
    data=args.firmware.read_bytes()
    if len(data)!=0xE0000 or hashlib.sha256(data).hexdigest()!=SHA:
        raise SystemExit("Refusing an image other than verified ASUS V020")
    thunks=inventory(data)
    decoded,*_=traverse(data,thunks); decoded=set(decoded)
    if args.summary:
        edges={f'{b}:{pc:04X}':[f'{cb}:{cp:04X}' for cb,cp,_ in incoming_exact(data,decoded,thunks,(b,pc))]
               for b,pc in [(9,0xE703),(9,0xEBE1)]}
        assert edges == {'9:E703':['9:E7F2'],'9:EBE1':['9:E759']}, edges
        assert resolved_target(data,thunks,9,0xE7F5)==(13,0x3DE6)
        chunk=data[9*BANK_SIZE:10*BANK_SIZE]
        assert chunk[0xE75C:0xE760]==bytes.fromhex('AD07801C')
        assert chunk[0xE77C:0xE77F]==bytes.fromhex('AF0522')
        args.summary.write_text(json.dumps({'firmware_sha256':SHA,
            'decoded_incoming_sites':edges,
            'return_route':['9:EBE1 -> R7','9:E75C R5=R7','9:E77C R7=R5; RET',
                            '9:E7F2 calls E703','9:E7F5 calls 13:3DE6'],
            'conclusion':'Known EBE1 return route feeds the already identified display/scaler sink.',
            'limits':'Decoded direct edges only; not proof against indirect entries, packed-state copies or consumers of setting query selectors 04/43.'},indent=2)+'\n')

    print("ASUS MB16AMT V020 — charge-policy caller/return trace")
    print(f"SHA256: {SHA}")
    print("READ-ONLY OFFLINE ANALYSIS; NO DEVICE I/O\n")
    print("===== FIXED PROVENANCE =====")
    print("Set-VCP ED -> D9FF.bit7 (active-high charge-from-NB/PC allowed)")
    print("9:E703 and 9:EBE1 both evaluate D9FF.bit7 and return status via R5/R7")
    print()

    print("===== EXACT INCOMING CALLS TO POLICY TARGETS =====")
    for target in TARGETS:
        print(f"-- target {target[0]}:{target[1]:04X} --")
        rows=incoming_exact(data,decoded,thunks,target)
        if not rows: print("(none decoded)")
        for b,pc,text in rows:
            print(f"{b}:{pc:04X}  {text}")
    print()

    for bank,lo,hi,label in REGIONS:
        print(f"===== {label.upper()} =====")
        print_region(data,decoded,thunks,bank,lo,hi)
        print("-- XDATA refs --")
        for pc,addr in dptr_refs(data,decoded,bank,lo,hi):
            print(f"{bank}:{pc:04X} -> {addr:04X}")
        print()

    # Expand every external caller of E759/E7F2 by a compact +/-0x50 window.
    seen=set()
    print("===== CALLER WINDOWS FOR E759/E7F2 =====")
    for target in [(9,0xE759),(9,0xE7F2)]:
        for b,pc,_ in incoming_exact(data,decoded,thunks,target):
            key=(b,max(0,pc-0x50),min(0x10000,pc+0x70))
            if key in seen: continue
            seen.add(key)
            print(f"-- caller around {b}:{pc:04X} -> {target[0]}:{target[1]:04X} --")
            print_region(data,decoded,thunks,*key)
    if not seen: print("(none outside bridge)")
    print()

    print("===== STATUS-CODE CLUES =====")
    print("Look for immediate post-call tests/moves of R5 or R7 after E703/EBE1.")
    print("If status 0/6 gates hardware-facing calls or Type-C/PMIC state, that is the next promoted bridge.")
    return 0

if __name__=="__main__":
    raise SystemExit(main())

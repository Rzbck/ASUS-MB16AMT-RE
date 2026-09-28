"""Trace the small set of 99/100/101 guards near OSD activity in ASUS MB16AMT V020.

Read-only/offline. This is deliberately narrow: it does not revisit VCP ED/charge
policy. It asks which value is actually compared with ~100 and what OSD/XDATA
state is touched immediately around that comparison.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib

from analyze_banked_abi import BANK_SIZE, LENGTHS, SHA, inventory, traverse, word
from mcs51 import decode

GUARDS = [
    (1, 0xF13B), (1, 0xF16C), (1, 0xF1A5), (1, 0xF3BE),
    (1, 0xF7D6), (10, 0xBD31), (10, 0xF3DA), (10, 0xF403),
]
OSD_LO, OSD_HI = 0xD838, 0xD84F

CONTROL = {
    0x02,0x12,0x22,0x32,0x73,0x40,0x50,0x60,0x70,0x80,
    0x10,0x20,0x30,0xD5,
}


def starts_for(decoded, bank: int) -> list[int]:
    return sorted(pc for b, pc in decoded if b == bank)


def fmt(data: bytes, bank: int, pc: int, thunks) -> str:
    chunk = data[bank*BANK_SIZE:(bank+1)*BANK_SIZE]
    text = decode(chunk, pc)
    if chunk[pc] in (0x02,0x12):
        target = word(chunk, pc+1)
        if target in thunks:
            b,a = thunks[target]
            text += f" ; -> {b}:{a:04X}"
    return text


def is_control(op: int) -> bool:
    return op in CONTROL or 0xB4 <= op <= 0xBF or 0xD8 <= op <= 0xDF or (op & 0x1F) in (0x01,0x11)


def previous_starts(starts: list[int], pc: int, count: int = 24) -> list[int]:
    rows = [x for x in starts if x < pc]
    return rows[-count:]


def nearest_dptr_source(chunk: bytes, starts: list[int], movx_pc: int):
    """Find a straight-line MOV DPTR,#imm feeding a MOVX A,@DPTR."""
    prev = previous_starts(starts, movx_pc, 20)
    for p in reversed(prev):
        op = chunk[p]
        if op == 0x90:
            return p, word(chunk, p+1)
        if p != prev[-1] and (is_control(op) or op == 0xA3):
            break
    return None


def trace_a_source(chunk: bytes, starts: list[int], guard_pc: int):
    """Conservative local provenance for A at a guard.

    Stops at control-flow boundaries. Handles the common direct MOVX/MOV forms
    needed for triage; unknown means unknown rather than guessed.
    """
    prev = previous_starts(starts, guard_pc, 30)
    for p in reversed(prev):
        op = chunk[p]
        if is_control(op):
            break
        if op == 0xE0:  # MOVX A,@DPTR
            src = nearest_dptr_source(chunk, starts, p)
            if src:
                dpc, addr = src
                return f"MOVX A,@DPTR at {p:04X}, DPTR from {dpc:04X} => XDATA {addr:04X}"
            return f"MOVX A,@DPTR at {p:04X}, DPTR source unresolved"
        if op == 0xE5:  # MOV A,direct
            return f"MOV A,{chunk[p+1]:02X}h at {p:04X}"
        if 0xE8 <= op <= 0xEF:  # MOV A,Rn
            rn = op & 7
            return f"MOV A,R{rn} at {p:04X} (register provenance requires caller/local trace)"
        if op == 0x74:
            return f"MOV A,#{chunk[p+1]:02X}h at {p:04X}"
        # Arithmetic means A was transformed locally; report nearest transform.
        if op in (0x24,0x34,0x44,0x54,0x64,0x94,0xC4,0x03,0x13,0x23,0x33):
            try:
                return f"A transformed at {p:04X}: {decode(chunk,p)}"
            except Exception:
                return f"A transformed at {p:04X}"
    return "unresolved in same straight-line basic block"


def local_xdata(data: bytes, decoded, bank: int, lo: int, hi: int):
    chunk = data[bank*BANK_SIZE:(bank+1)*BANK_SIZE]
    out=[]
    for pc in starts_for(decoded, bank):
        if lo <= pc < hi and chunk[pc] == 0x90:
            out.append((pc, word(chunk,pc+1)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("firmware", type=Path)
    args = ap.parse_args()

    data = args.firmware.read_bytes()
    if len(data) != 0xE0000 or hashlib.sha256(data).hexdigest() != SHA:
        raise SystemExit("Refusing an image other than verified ASUS V020")

    thunks = inventory(data)
    decoded, *_ = traverse(data, thunks)
    decoded_set=set(decoded)

    print("ASUS MB16AMT V020 — focused SOC 99/100 guard trace")
    print(f"SHA256: {SHA}")
    print("READ-ONLY OFFLINE ANALYSIS; NO DEVICE I/O")
    print("Scope: battery/SOC OSD only; charge-policy branch excluded")

    for bank, guard in GUARDS:
        print()
        print(f"===== GUARD {bank}:{guard:04X} =====")
        if (bank,guard) not in decoded_set:
            print("not a decoded instruction boundary")
            continue
        chunk=data[bank*BANK_SIZE:(bank+1)*BANK_SIZE]
        print("instruction:", fmt(data,bank,guard,thunks))
        print("A provenance:", trace_a_source(chunk, starts_for(decoded,bank), guard))

        lo=max(0,guard-0x60); hi=min(0x10000,guard+0x90)
        refs=local_xdata(data,decoded,bank,lo,hi)
        if refs:
            print("nearby XDATA:")
            seen=set()
            for pc,addr in refs:
                key=(pc,addr)
                if key in seen: continue
                seen.add(key)
                tag=" [OSD scratch]" if OSD_LO <= addr <= OSD_HI else ""
                print(f"  {bank}:{pc:04X} -> {addr:04X}{tag}")

        print("context:")
        for pc in starts_for(decoded,bank):
            if lo <= pc < hi:
                mark=" >>>" if pc==guard else ""
                print(f"  {bank}:{pc:04X}  {fmt(data,bank,pc,thunks)}{mark}")

    print()
    print("===== DECISION RULE =====")
    print("A SOC candidate must show a real 0..100 state value flowing toward digit/OSD construction.")
    print("Reject guards that only bound geometry, indices, timeouts, coordinates, or table selection.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

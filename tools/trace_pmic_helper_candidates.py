"""Trace candidate PMIC helper call conventions in verified ASUS MB16AMT V020.

Read-only/offline. No device access.

This follows up trace_pmic_i2c_candidates.py. The first pass found a notable
call at 7:7A95 with a nearby setup containing E0/01/08 before helper 7:8480.
Because MCS-51 compiler calling conventions can make any one register ambiguous,
this tool inspects *all* decoded callers of the strongest helper candidates,
reconstructs recent immediate R0..R7 setup, and prints helper bodies/XDATA refs.

Hypothesis only: RL6492 reference firmware can use a SY9329-like PMIC at 8-bit
slave 0xE0, with VBUS/current ADC registers 0x07/0x08. Do not treat matches as
proof until the helper reaches hardware I2C or the runtime values correlate.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib

from analyze_banked_abi import BANK_SIZE, LENGTHS, SHA, inventory, traverse, word
from mcs51 import decode

HELPERS = [
    (7, 0x8480, "candidate_from_7_7A95"),
    (5, 0xEEE1, "candidate_from_7_D7ED"),
    (13, 0x6771, "candidate_from_13_5F04"),
    (13, 0x49E3, "candidate_from_10_F2E6"),
]


def signed8(v: int) -> int:
    return v - 0x100 if v & 0x80 else v


def direct_target(data: bytes, bank: int, pc: int):
    c = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    op = c[pc]
    n = LENGTHS[op]
    nxt = (pc + n) & 0xFFFF
    if op in (0x02, 0x12):
        return word(c, pc + 1)
    if op & 0x1F in (0x01, 0x11):
        return (nxt & 0xF800) | ((op & 0xE0) << 3) | c[pc + 1]
    if op in {0x10,0x20,0x30,0x40,0x50,0x60,0x70,0x80,0xD5,0xD8,0xD9,0xDA,0xDB,0xDC,0xDD,0xDE,0xDF} or 0xB4 <= op <= 0xBF:
        return (nxt + signed8(c[pc + n - 1])) & 0xFFFF
    return None


def resolved_target(data: bytes, thunks, bank: int, pc: int):
    c = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    op = c[pc]
    t = direct_target(data, bank, pc)
    if t is None:
        return None
    if op in (0x02, 0x12) or op & 0x1F in (0x01, 0x11):
        return thunks.get(t, (bank, t))
    return bank, t


def is_call(data: bytes, bank: int, pc: int) -> bool:
    op = data[bank * BANK_SIZE + pc]
    return op == 0x12 or op & 0x1F == 0x11


def starts_by_bank(decoded):
    out = {}
    for b, pc in sorted(decoded):
        out.setdefault(b, []).append(pc)
    return out


def neighborhood(starts, bank, pc, before=14, after=8):
    xs = starts.get(bank, [])
    try:
        i = xs.index(pc)
    except ValueError:
        return []
    return xs[max(0, i-before):min(len(xs), i+after+1)]


def reg_imm(data: bytes, bank: int, pc: int):
    """Return (reg,imm) for MOV Rn,#imm, else None."""
    c = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    op = c[pc]
    if 0x78 <= op <= 0x7F:
        return op & 7, c[pc + 1]
    return None


def recent_reg_setup(data, starts, bank, call_pc, limit=18):
    regs = {}
    rows = neighborhood(starts, bank, call_pc, limit, 0)[:-1]
    for q in rows:
        ri = reg_imm(data, bank, q)
        if ri:
            regs[ri[0]] = (q, ri[1])
    return regs


def format_regs(regs):
    if not regs:
        return "(none)"
    return " ".join(f"R{r}={v:02X}@{pc:04X}" for r, (pc, v) in sorted(regs.items()))


def print_window(data, thunks, starts, bank, pc, before=14, after=8):
    c = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    for q in neighborhood(starts, bank, pc, before, after):
        text = decode(c, q)
        if is_call(data, bank, q):
            t = resolved_target(data, thunks, bank, q)
            if t:
                text += f" ; CALL -> {t[0]}:{t[1]:04X}"
        mark = ">>" if q == pc else "  "
        print(f"{mark} {bank}:{q:04X}  {text}")


def helper_region(data, thunks, decoded, bank, target, span=0x120):
    print(f"-- body neighborhood {bank}:{target:04X}..{min(0x10000,target+span):04X} --")
    c = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    refs = []
    calls = []
    for pc in sorted(p for b, p in decoded if b == bank and target <= p < min(0x10000, target + span)):
        text = decode(c, pc)
        if c[pc] == 0x90:
            refs.append((pc, word(c, pc + 1)))
        if is_call(data, bank, pc):
            t = resolved_target(data, thunks, bank, pc)
            if t:
                calls.append((pc, t))
                text += f" ; CALL -> {t[0]}:{t[1]:04X}"
        print(f"   {bank}:{pc:04X}  {text}")
    if refs:
        print("  XDATA/DPTR immediates:")
        for pc, addr in refs:
            tag = " hardware-ish" if addr >= 0xF000 or 0xB000 <= addr < 0xC000 else ""
            print(f"    {bank}:{pc:04X} -> {addr:04X}{tag}")
    if calls:
        print("  outgoing calls:")
        for pc, (tb, tp) in calls:
            print(f"    {bank}:{pc:04X} -> {tb}:{tp:04X}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("firmware", type=Path)
    ap.add_argument("--body-span", type=lambda x: int(x, 0), default=0x120)
    args = ap.parse_args()

    data = args.firmware.read_bytes()
    if len(data) != 0xE0000 or hashlib.sha256(data).hexdigest() != SHA:
        raise SystemExit("Refusing an image other than verified ASUS V020")

    thunks = inventory(data)
    decoded, *_ = traverse(data, thunks)
    decoded = set(decoded)
    starts = starts_by_bank(decoded)

    print("ASUS MB16AMT V020 — PMIC helper candidate trace")
    print(f"SHA256: {SHA}")
    print("READ-ONLY OFFLINE ANALYSIS; NO DEVICE I/O")
    print("Reference hypothesis only: 0xE0 / SY9329-like PMIC; 0x07 VBUS, 0x08 current")
    print()

    for hb, hp, label in HELPERS:
        print(f"===== HELPER {hb}:{hp:04X} {label} =====")
        callers = []
        for b, pc in sorted(decoded):
            if is_call(data, b, pc) and resolved_target(data, thunks, b, pc) == (hb, hp):
                callers.append((b, pc))
        print(f"decoded_callers={len(callers)}")
        for b, pc in callers:
            regs = recent_reg_setup(data, starts, b, pc)
            vals = {v for _, v in regs.values()}
            flags = []
            if 0xE0 in vals: flags.append("HAS_E0")
            if 0x08 in vals: flags.append("HAS_08")
            if 0x07 in vals: flags.append("HAS_07")
            if 0x06 in vals: flags.append("HAS_06")
            if 0x01 in vals: flags.append("HAS_01")
            print(f"-- caller {b}:{pc:04X} regs[{format_regs(regs)}] {' '.join(flags)} --")
            print_window(data, thunks, starts, b, pc, 16, 5)
            print()
        helper_region(data, thunks, decoded, hb, hp, args.body_span)
        print()

    print("===== TARGETED INTERPRETATION =====")
    print("Promote 7:8480 only if its callers show a stable argument role for E0 and 06/07/08,")
    print("and its body/outgoing calls reach hardware-I2C state/registers rather than generic UI/data code.")
    print("Do not write PMIC registers; the next live step should be read-only ADC/status exposure only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Find PMIC / VBUS I2C candidates in verified ASUS MB16AMT V020 firmware.

Read-only/offline. This tool does not touch the monitor.

Primary hypotheses:
- RL6492 reference designs use a SY9329 Type-C PMIC at 8-bit I2C address 0xE0.
- The SY9329 register map uses 0x00..0x08, with read-only ADC/status at
  0x04..0x08 and VBUS/current at 0x07/0x08.
- ASUS may reuse the already-identified generic internal I2C helper 0:6D00,
  or a separate HW-I2C helper. We therefore inspect both:
    1) every decoded caller of 0:6D00 and its setup window;
    2) every decoded immediate 0xE0 load, ranked by nearby sub-registers,
       lengths and calls;
    3) neighborhoods containing the distinctive register trio 0x06/0x07/0x08.

The output is candidate evidence only. It must not be interpreted as proof that
MB16AMT actually uses SY9329 until an ASUS path is traced to hardware I/O.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib

from analyze_banked_abi import BANK_SIZE, LENGTHS, SHA, inventory, traverse, word
from mcs51 import decode

GENERIC_I2C_TARGET = (0, 0x6D00)
PMIC_ADDR = 0xE0
PMIC_REGS = set(range(0x00, 0x09))
ADC_REGS = {0x04, 0x05, 0x06, 0x07, 0x08}


def signed8(v: int) -> int:
    return v - 0x100 if v & 0x80 else v


def direct_target(data: bytes, bank: int, pc: int):
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


def resolved_target(data: bytes, thunks, bank: int, pc: int):
    chunk = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    op = chunk[pc]
    t = direct_target(data, bank, pc)
    if t is None:
        return None
    if op in (0x02, 0x12) or op & 0x1F in (0x01, 0x11):
        return thunks.get(t, (bank, t))
    return bank, t


def is_call(data: bytes, bank: int, pc: int) -> bool:
    op = data[bank * BANK_SIZE + pc]
    return op == 0x12 or op & 0x1F == 0x11


def imm8(data: bytes, bank: int, pc: int):
    """Return 8-bit immediate for common MOV/CJNE forms, else None."""
    c = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    op = c[pc]
    if op == 0x74:                 # MOV A,#imm
        return c[pc + 1]
    if op == 0x75:                 # MOV direct,#imm
        return c[pc + 2]
    if 0x76 <= op <= 0x7F:         # MOV @Ri/Rn,#imm
        return c[pc + 1]
    if op in (0xB4, 0xB6, 0xB7) or 0xB8 <= op <= 0xBF:  # CJNE x,#imm,rel
        return c[pc + 1]
    return None


def starts_by_bank(decoded):
    out = {}
    for b, pc in sorted(decoded):
        out.setdefault(b, []).append(pc)
    return out


def neighborhood(starts, bank, pc, before=10, after=14):
    xs = starts.get(bank, [])
    try:
        i = xs.index(pc)
    except ValueError:
        return []
    return xs[max(0, i-before):min(len(xs), i+after+1)]


def print_window(data, thunks, starts, bank, pc, before=10, after=14):
    for q in neighborhood(starts, bank, pc, before, after):
        text = decode(data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE], q)
        t = resolved_target(data, thunks, bank, q)
        if t and is_call(data, bank, q):
            text += f" ; CALL -> {t[0]}:{t[1]:04X}"
        mark = ">>" if q == pc else "  "
        print(f"{mark} {bank}:{q:04X}  {text}")


def extract_features(data, thunks, starts, bank, pc):
    vals = []
    calls = []
    for q in neighborhood(starts, bank, pc, 12, 18):
        v = imm8(data, bank, q)
        if v is not None:
            vals.append((q, v))
        if is_call(data, bank, q):
            t = resolved_target(data, thunks, bank, q)
            if t:
                calls.append((q, t))
    regset = {v for _, v in vals if v in PMIC_REGS}
    score = 0
    if any(v == PMIC_ADDR for _, v in vals): score += 8
    if 0x07 in regset: score += 4
    if 0x08 in regset: score += 4
    if 0x06 in regset: score += 2
    if len(ADC_REGS & regset) >= 3: score += 5
    if any(v in (1, 2, 4) for _, v in vals): score += 1
    if calls: score += min(4, len(calls))
    if any(t == GENERIC_I2C_TARGET for _, t in calls): score += 10
    return score, vals, calls, regset


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("firmware", type=Path)
    ap.add_argument("--top", type=int, default=30, help="number of 0xE0 candidates to print")
    args = ap.parse_args()

    data = args.firmware.read_bytes()
    if len(data) != 0xE0000 or hashlib.sha256(data).hexdigest() != SHA:
        raise SystemExit("Refusing an image other than verified ASUS V020")

    thunks = inventory(data)
    decoded, *_ = traverse(data, thunks)
    decoded = set(decoded)
    starts = starts_by_bank(decoded)

    print("ASUS MB16AMT V020 — PMIC / VBUS I2C candidate trace")
    print(f"SHA256: {SHA}")
    print("READ-ONLY OFFLINE ANALYSIS; NO DEVICE I/O")
    print("Reference hypothesis only: SY9329-like PMIC at 8-bit slave 0xE0, regs 0x00..0x08")
    print()

    print("===== ALL DECODED CALLERS OF GENERIC INTERNAL I2C 0:6D00 =====")
    callers = []
    for b, pc in sorted(decoded):
        if is_call(data, b, pc) and resolved_target(data, thunks, b, pc) == GENERIC_I2C_TARGET:
            callers.append((b, pc))
    print(f"count={len(callers)}")
    for b, pc in callers:
        _, vals, _, regs = extract_features(data, thunks, starts, b, pc)
        imm_text = " ".join(f"{q:04X}:{v:02X}" for q, v in vals)
        print(f"-- caller {b}:{pc:04X} nearby_immediates=[{imm_text}] pmic_regs={sorted(regs)} --")
        print_window(data, thunks, starts, b, pc, 12, 4)
        print()

    print("===== RANKED IMMEDIATE 0xE0 LOADS =====")
    candidates = []
    for b, pc in sorted(decoded):
        if imm8(data, b, pc) != PMIC_ADDR:
            continue
        score, vals, calls, regs = extract_features(data, thunks, starts, b, pc)
        candidates.append((score, b, pc, vals, calls, regs))
    candidates.sort(key=lambda x: (-x[0], x[1], x[2]))
    print(f"decoded_E0_immediates={len(candidates)}")
    for score, b, pc, vals, calls, regs in candidates[:args.top]:
        call_text = ", ".join(f"{q:04X}->{tb}:{tp:04X}" for q, (tb, tp) in calls)
        print(f"-- score={score} candidate {b}:{pc:04X} regs={sorted(regs)} calls=[{call_text}] --")
        print_window(data, thunks, starts, b, pc, 10, 16)
        print()

    print("===== DISTINCTIVE 0x06/0x07/0x08 NEIGHBORHOODS =====")
    seen = set()
    hits = 0
    for b, pcs in starts.items():
        for pc in pcs:
            vals = [imm8(data, b, q) for q in neighborhood(starts, b, pc, 8, 8)]
            s = {v for v in vals if v is not None}
            if not {0x06,0x07,0x08}.issubset(s):
                continue
            key = (b, pc // 0x20)
            if key in seen:
                continue
            seen.add(key); hits += 1
            print(f"-- trio candidate {b}:{pc:04X} values={sorted(v for v in s if v <= 0x20)} --")
            print_window(data, thunks, starts, b, pc, 10, 10)
            print()
    if not hits:
        print("(no decoded neighborhood contained immediate 06/07/08 trio)")

    print("===== INTERPRETATION =====")
    print("STRONG: setup with slave 0xE0 plus regs 0x07/0x08 reaching a repeated I2C helper.")
    print("VERY STRONG: same setup reaches confirmed 0:6D00 or an independently mapped HW-I2C helper.")
    print("Do not perform writes to candidate PMIC registers until the exact chip/path/current limits are proven.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

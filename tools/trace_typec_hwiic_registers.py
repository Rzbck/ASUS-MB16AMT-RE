"""Trace RL6492 Type-C HW-I2C register fingerprints in verified MB16AMT V020.

Read-only/offline. No device access.

The public RL6492 reference implementation maps the Type-C PMIC hardware-I2C
controller at XDATA 0x7F60..0x7F6A. In particular:
  0x7F60 I2CM_CR0
  0x7F61 I2CM_CR1
  0x7F62 I2CM_CR2
  0x7F63 I2CM_CR3
  0x7F64..0x7F67 timing registers
  0x7F69 I2CM_TD (TX/data FIFO)
  0x7F6A I2CM_CCR

This is a much stronger fingerprint for the PMIC path than an isolated 0xE0
immediate. The tool finds every decoded MOV DPTR,#7F6x reference, groups nearby
hits, ranks dense groups, and prints compact disassembly around them.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib

from analyze_banked_abi import BANK_SIZE, LENGTHS, SHA, inventory, traverse, word
from mcs51 import decode

HW_LO = 0x7F60
HW_HI = 0x7F6A
NAMES = {
    0x7F60: "I2CM_CR0",
    0x7F61: "I2CM_CR1",
    0x7F62: "I2CM_CR2",
    0x7F63: "I2CM_CR3",
    0x7F64: "I2CM_STR0",
    0x7F65: "I2CM_STR1",
    0x7F66: "I2CM_STR2",
    0x7F67: "I2CM_STR3",
    0x7F68: "I2CM_SR/BUF",
    0x7F69: "I2CM_TD",
    0x7F6A: "I2CM_CCR",
}


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
    return None


def resolved_target(data: bytes, thunks, bank: int, pc: int):
    t = direct_target(data, bank, pc)
    if t is None:
        return None
    return thunks.get(t, (bank, t))


def is_call(data: bytes, bank: int, pc: int) -> bool:
    op = data[bank * BANK_SIZE + pc]
    return op == 0x12 or op & 0x1F == 0x11


def starts_by_bank(decoded):
    out = {}
    for b, pc in sorted(decoded):
        out.setdefault(b, []).append(pc)
    return out


def mov_dptr_imm(data: bytes, bank: int, pc: int):
    c = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    if c[pc] == 0x90:
        return word(c, pc + 1)
    return None


def window(starts, bank, pc, before=8, after=10):
    xs = starts.get(bank, [])
    try:
        i = xs.index(pc)
    except ValueError:
        return []
    return xs[max(0, i-before):min(len(xs), i+after+1)]


def print_window(data, thunks, starts, bank, pc, before=8, after=10):
    c = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    for q in window(starts, bank, pc, before, after):
        text = decode(c, q)
        if is_call(data, bank, q):
            t = resolved_target(data, thunks, bank, q)
            if t:
                text += f" ; CALL -> {t[0]}:{t[1]:04X}"
        mark = ">>" if q == pc else "  "
        print(f"{mark} {bank}:{q:04X}  {text}")


def score_regs(regs):
    s = len(regs) * 2
    if 0x7F69 in regs: s += 12
    if 0x7F60 in regs: s += 6
    if 0x7F63 in regs: s += 5
    if 0x7F6A in regs: s += 4
    if len(regs) >= 5: s += 8
    if {0x7F60, 0x7F63, 0x7F69}.issubset(regs): s += 15
    return s


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("firmware", type=Path)
    ap.add_argument("--gap", type=lambda x: int(x, 0), default=0x180,
                    help="max PC gap when grouping register references")
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()

    data = args.firmware.read_bytes()
    if len(data) != 0xE0000 or hashlib.sha256(data).hexdigest() != SHA:
        raise SystemExit("Refusing an image other than verified ASUS V020")

    thunks = inventory(data)
    decoded, *_ = traverse(data, thunks)
    decoded = set(decoded)
    starts = starts_by_bank(decoded)

    hits = []
    for b, pc in sorted(decoded):
        addr = mov_dptr_imm(data, b, pc)
        if addr is not None and HW_LO <= addr <= HW_HI:
            hits.append((b, pc, addr))

    print("ASUS MB16AMT V020 — RL6492 Type-C HW-I2C register trace")
    print(f"SHA256: {SHA}")
    print("READ-ONLY OFFLINE ANALYSIS; NO DEVICE I/O")
    print(f"decoded 0x7F60..0x7F6A DPTR references={len(hits)}")
    print()

    if not hits:
        print("NO_MATCH: no decoded direct references to the RL6492 reference HW-I2C range.")
        print("This would mean ASUS either uses a different map/path or accesses it indirectly.")
        return 0

    # Group nearby refs within a bank.
    groups = []
    cur = []
    for h in hits:
        if not cur or (h[0] == cur[-1][0] and h[1] - cur[-1][1] <= args.gap):
            cur.append(h)
        else:
            groups.append(cur); cur = [h]
    if cur:
        groups.append(cur)

    ranked = []
    for g in groups:
        regs = {a for _, _, a in g}
        ranked.append((score_regs(regs), g, regs))
    ranked.sort(key=lambda x: (-x[0], x[1][0][0], x[1][0][1]))

    print("===== RANKED HW-I2C REGISTER CLUSTERS =====")
    for i, (score, g, regs) in enumerate(ranked[:args.top], 1):
        b = g[0][0]
        lo, hi = g[0][1], g[-1][1]
        regtxt = ", ".join(f"{a:04X}:{NAMES.get(a,'?')}" for a in sorted(regs))
        print(f"#{i} score={score} bank={b} pc={lo:04X}..{hi:04X} refs={len(g)} regs=[{regtxt}]")
        for _, pc, addr in g:
            print(f"  HIT {b}:{pc:04X} -> {addr:04X} {NAMES.get(addr,'?')}")
        print()

    print("===== DETAILED WINDOWS FOR HIGH-VALUE HITS =====")
    shown = set()
    # Prioritize TD, CR0, CR3, CCR, then everything else in top clusters.
    priority = [0x7F69, 0x7F60, 0x7F63, 0x7F6A]
    ordered = []
    for _, g, _ in ranked[:min(args.top, 8)]:
        for want in priority:
            ordered += [h for h in g if h[2] == want]
        ordered += [h for h in g if h[2] not in priority]
    for b, pc, addr in ordered:
        key = (b, pc)
        if key in shown:
            continue
        shown.add(key)
        print(f"-- {b}:{pc:04X} MOV DPTR,#{addr:04X} ({NAMES.get(addr,'?')}) --")
        print_window(data, thunks, starts, b, pc, 10, 14)
        print()
        if len(shown) >= 30:
            break

    print("===== INTERPRETATION GATE =====")
    print("VERY STRONG PMIC-HW-I2C fingerprint: one compact routine touches 7F60 + 7F63 + 7F69")
    print("and preferably 7F6A / timing registers, with repeated writes/reads of 7F69 as a FIFO.")
    print("Once found, trace its callers for slave/subaddress/length and only then attempt read-only live PMIC ADC access.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

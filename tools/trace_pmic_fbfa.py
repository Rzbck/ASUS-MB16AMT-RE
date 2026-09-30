"""Focused offline trace of logical helper 9:FBFA in ASUS MB16AMT V020.

Read-only/offline. No device access. This helper is the current priority because
wrappers 13:6771 and 13:49E3 both converge on it after loading R7=0x08.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib

from analyze_banked_abi import SHA, inventory, traverse
from trace_pmic_helper_candidates import (
    is_call,
    resolved_target,
    starts_by_bank,
    recent_reg_setup,
    format_regs,
    print_window,
    helper_region,
)

TARGET = (9, 0xFBFA)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("firmware", type=Path)
    ap.add_argument("--body-span", type=lambda x: int(x, 0), default=0x300)
    args = ap.parse_args()

    data = args.firmware.read_bytes()
    if len(data) != 0xE0000 or hashlib.sha256(data).hexdigest() != SHA:
        raise SystemExit("Refusing an image other than verified ASUS V020")

    thunks = inventory(data)
    decoded, *_ = traverse(data, thunks)
    decoded = set(decoded)
    starts = starts_by_bank(decoded)

    print("ASUS MB16AMT V020 — focused PMIC candidate 9:FBFA")
    print(f"SHA256: {SHA}")
    print("READ-ONLY OFFLINE ANALYSIS; NO DEVICE I/O")
    print()

    callers = []
    for b, pc in sorted(decoded):
        if is_call(data, b, pc) and resolved_target(data, thunks, b, pc) == TARGET:
            callers.append((b, pc))

    print(f"===== DIRECT CALLERS OF {TARGET[0]}:{TARGET[1]:04X} =====")
    print(f"decoded_callers={len(callers)}")
    for b, pc in callers:
        regs = recent_reg_setup(data, starts, b, pc, 30)
        vals = {v for _, v in regs.values()}
        flags = []
        for v, name in ((0xE0,'E0'),(0x08,'08'),(0x07,'07'),(0x06,'06'),(0x01,'01')):
            if v in vals:
                flags.append('HAS_' + name)
        print(f"-- caller {b}:{pc:04X} regs[{format_regs(regs)}] {' '.join(flags)} --")
        print_window(data, thunks, starts, b, pc, 28, 8)
        print()

    print(f"===== BODY {TARGET[0]}:{TARGET[1]:04X} =====")
    helper_region(data, thunks, decoded, TARGET[0], TARGET[1], args.body_span)
    print()
    print("===== INTERPRETATION GATE =====")
    print("Promote as PMIC/HW-I2C only if the body or descendants reach a coherent hardware-I2C/Type-C register path.")
    print("Do not infer that an immediate 0xE0 alone is an I2C slave address.")
    print("No PMIC writes until the chip/path/current-limit semantics are proven.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

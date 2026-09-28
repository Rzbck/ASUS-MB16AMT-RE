"""Decode the confirmed ASUS V020 Set-VCP inline byte-switch at bank9:9468.

The repo's bounded 8051 interpreter already models LCALL 0x210D as a compiler
helper whose call-site payload is a sequence of (target16, key8) entries,
terminated by target16==0 followed by a default target16.  In the confirmed
Set-VCP handler, D993 (RxBuf[3], VCP opcode) is moved to A immediately before
LCALL 0x210D at 9:9468, so the inline payload beginning at 9:946B is the exact
VCP-opcode dispatch table.

Read-only/offline; no device access.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib
from collections import deque

from analyze_banked_abi import BANK_SIZE, LENGTHS, SHA, inventory, traverse, word
from mcs51 import decode

BANK = 9
CALL_SITE = 0x9468
TABLE = 0x946B
REGION_LO = 0x9452
REGION_HI = 0x9CA3
COMMON_STOPS = {0x9C99, 0x9CA2}


def instr(data, bank, pc):
    chunk = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    return decode(chunk, pc)


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


def parse_switch(chunk, pos):
    entries = []
    for _ in range(256):
        target = word(chunk, pos)
        if target == 0:
            default = word(chunk, pos + 2)
            return entries, default, pos + 4
        key = chunk[pos + 2]
        entries.append((key, target, pos))
        pos += 3
    raise RuntimeError("unterminated 0x210D inline byte switch")


def rel_target(chunk, pc):
    op = chunk[pc]
    n = LENGTHS[op]
    nxt = (pc + n) & 0xFFFF
    rel_ops = {
        0x10, 0x20, 0x30, 0x40, 0x50, 0x60, 0x70, 0x80,
        0xD5, 0xD8, 0xD9, 0xDA, 0xDB, 0xDC, 0xDD, 0xDE, 0xDF,
    }
    if op in rel_ops or 0xB4 <= op <= 0xBF:
        rel = chunk[pc + n - 1]
        if rel >= 0x80:
            rel -= 0x100
        return (nxt + rel) & 0xFFFF
    return None


def successors(chunk, pc):
    op = chunk[pc]
    n = LENGTHS[op]
    nxt = (pc + n) & 0xFFFF

    if op in (0x22, 0x32):
        return []
    if op == 0x02:  # LJMP
        return [word(chunk, pc + 1)]
    if op == 0x80:  # SJMP
        return [rel_target(chunk, pc)]
    if op & 0x1F == 0x01:  # AJMP
        return [(nxt & 0xF800) | ((op & 0xE0) << 3) | chunk[pc + 1]]

    # Conditional relative branches, including CJNE/DJNZ.
    if op in {0x10, 0x20, 0x30, 0x40, 0x50, 0x60, 0x70, 0xD5,
              0xD8, 0xD9, 0xDA, 0xDB, 0xDC, 0xDD, 0xDE, 0xDF} or 0xB4 <= op <= 0xBF:
        return [nxt, rel_target(chunk, pc)]

    # Calls return to fallthrough for local CFG purposes.
    return [nxt]


def reachable_block(decoded, chunk, start, limit=256):
    q = deque([start])
    seen = set()
    while q and len(seen) < limit:
        pc = q.popleft()
        if pc in seen or pc in COMMON_STOPS:
            continue
        if not (REGION_LO <= pc < REGION_HI) or (BANK, pc) not in decoded:
            continue
        seen.add(pc)
        for s in successors(chunk, pc):
            if s is not None and s not in seen:
                q.append(s)
    return sorted(seen)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("firmware", type=Path)
    ap.add_argument("--opcode", default="ED", help="hex VCP opcode to highlight (default ED)")
    args = ap.parse_args()

    data = args.firmware.read_bytes()
    if len(data) != 0xE0000 or hashlib.sha256(data).hexdigest() != SHA:
        raise SystemExit("Refusing an image other than verified ASUS V020")

    opcode = int(args.opcode, 16) & 0xFF
    thunks = inventory(data)
    decoded, edges, indirect, reserved, overlaps = traverse(data, thunks)
    decoded = set(decoded)
    chunk = data[BANK * BANK_SIZE:(BANK + 1) * BANK_SIZE]

    # Assert the confirmed call-site shape: MOV A,R7 ; LCALL 210D.
    if chunk[0x9467:0x946B] != bytes.fromhex("EF 12 21 0D"):
        raise SystemExit(f"Unexpected bytes at Set-VCP switch call: {chunk[0x9467:0x946B].hex(' ')}")

    entries, default, end = parse_switch(chunk, TABLE)
    mapping = {k: t for k, t, _ in entries}
    target = mapping.get(opcode, default)

    print("ASUS MB16AMT V020 — exact Set-VCP opcode switch")
    print(f"SHA256: {SHA}")
    print("READ-ONLY OFFLINE ANALYSIS; NO DEVICE I/O")
    print()
    print("===== PROVENANCE =====")
    print("D992 == 03 -> 9:9452 (confirmed Set-VCP handler)")
    print("9:9457 reads D993 -> R7; 9:9467 MOV A,R7; 9:9468 LCALL 210D")
    print(f"Inline byte-switch table starts at 9:{TABLE:04X} and ends at 9:{end:04X}")
    print(f"entries={len(entries)} default=9:{default:04X}")
    print()

    print("===== EXACT VCP OPCODE TABLE =====")
    for key, dst, pos in entries:
        mark = "  <== TARGET" if key == opcode else ""
        print(f"9:{pos:04X}  VCP {key:02X} -> 9:{dst:04X}{mark}")
    print(f"default -> 9:{default:04X}")
    print()

    print(f"===== VCP {opcode:02X} EXACT RESULT =====")
    if opcode in mapping:
        print(f"VCP {opcode:02X} has an explicit switch entry -> 9:{target:04X}")
    else:
        print(f"VCP {opcode:02X} has NO explicit entry; it uses default -> 9:{target:04X}")
    print()

    print(f"===== REACHABLE SET-VCP CODE FROM 9:{target:04X} =====")
    pcs = reachable_block(decoded, chunk, target)
    if not pcs:
        print("(target is outside decoded Set-VCP region or is a common epilogue)")
    else:
        for pc in pcs:
            text = instr(data, BANK, pc)
            extra = fmt_call(data, thunks, BANK, pc)
            if extra:
                text += f" ; {extra}"
            print(f"9:{pc:04X}  {text}")
    print()

    print("===== XDATA REFERENCES ON THAT REACHABLE PATH =====")
    refs = []
    for pc in pcs:
        if chunk[pc] == 0x90:
            addr = word(chunk, pc + 1)
            refs.append((pc, addr))
            print(f"9:{pc:04X} -> {addr:04X}")
    if not refs:
        print("(none)")
    print()

    print("===== CALLS/JUMPS ON THAT REACHABLE PATH =====")
    calls = 0
    for pc in pcs:
        extra = fmt_call(data, thunks, BANK, pc)
        if extra:
            calls += 1
            print(f"9:{pc:04X}  {extra}")
    if not calls:
        print("(none)")
    print()

    print("Interpretation rule: this table is promoted to exact VCP dispatch only because A is proven to come directly from D993 at the confirmed Set-VCP entry.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

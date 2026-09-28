"""Rank static candidates for the MB16AMT battery/SOC OSD path.

Read-only/offline. This intentionally ignores the already-solved VCP ED charge-policy
branch and targets only the displayed battery percentage path.

Signals used:
- decoded accesses to the known numeric OSD scratch D838..D84F;
- direct calls to the confirmed numeric renderer thunk 0x1670;
- local decimal conversion idioms (DIV AB with B=10 or B=100);
- nearby guards/comparisons against 100/101.

The output is a ranked shortlist with local disassembly and XDATA references. It is
an evidence collector, not an automatic claim that any candidate is SOC.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import hashlib

from analyze_banked_abi import BANK_SIZE, LENGTHS, SHA, inventory, traverse, word
from mcs51 import decode

SCRATCH_LO = 0xD838
SCRATCH_HI = 0xD84F
RENDER_THUNK = 0x1670
KNOWN_RENDERER_BANK = 1
KNOWN_RENDERER_LO = 0xEA00
KNOWN_RENDERER_HI = 0xED20


@dataclass(frozen=True)
class Seed:
    bank: int
    pc: int
    kind: str
    detail: str
    weight: int


def decoded_starts(decoded, bank: int) -> list[int]:
    return sorted(pc for b, pc in decoded if b == bank)


def fmt_insn(data: bytes, bank: int, pc: int, thunks) -> str:
    chunk = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    text = decode(chunk, pc)
    op = chunk[pc]
    if op in (0x02, 0x12):
        target = word(chunk, pc + 1)
        if target in thunks:
            tb, tp = thunks[target]
            text += f" ; -> {tb}:{tp:04X}"
    return text


def scratch_access(data: bytes, decoded_set: set[tuple[int, int]], bank: int, pc: int):
    """Classify a short straight-line access after MOV DPTR,#scratch_addr."""
    chunk = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    if chunk[pc] != 0x90:
        return []
    dptr = word(chunk, pc + 1)
    if not (SCRATCH_LO <= dptr <= SCRATCH_HI):
        return []
    out = []
    cur = pc
    for _ in range(10):
        if (bank, cur) not in decoded_set:
            break
        op = chunk[cur]
        n = LENGTHS[op]
        if op == 0x90:
            if cur != pc:
                break
            dptr = word(chunk, cur + 1)
        elif op == 0xA3:
            dptr = (dptr + 1) & 0xFFFF
        elif op == 0xE0:
            if SCRATCH_LO <= dptr <= SCRATCH_HI:
                out.append((cur, dptr, "READ"))
        elif op == 0xF0:
            if SCRATCH_LO <= dptr <= SCRATCH_HI:
                out.append((cur, dptr, "WRITE"))
        elif op in (0x02, 0x12, 0x22, 0x32, 0x73, 0x40, 0x50, 0x60, 0x70, 0x80, 0x10, 0x20, 0x30, 0xD5) or 0xB4 <= op <= 0xBF or 0xD8 <= op <= 0xDF or op & 0x1F in (0x01, 0x11):
            break
        cur += n
    return out


def b_immediate_before_div(data: bytes, starts: list[int], idx: int):
    """Return (pc,value) for nearby MOV B,#imm before DIV AB, if present."""
    chunk = data
    for j in range(max(0, idx - 8), idx):
        pc = starts[j]
        # MOV direct,#imm ; direct F0 is B register
        if chunk[pc] == 0x75 and chunk[pc + 1] == 0xF0:
            return pc, chunk[pc + 2]
    return None


def guard_value(chunk: bytes, pc: int):
    op = chunk[pc]
    # ADD/ADDC/XRL/SUBB A,#imm and CJNE A,#imm,rel
    if op in (0x24, 0x34, 0x64, 0x94, 0xB4):
        v = chunk[pc + 1]
        if v in (0x63, 0x64, 0x65):
            return v
    return None


def nearby_xdata_refs(data: bytes, decoded, bank: int, lo: int, hi: int):
    chunk = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    refs = []
    for pc in decoded_starts(decoded, bank):
        if pc < lo or pc >= hi:
            continue
        if chunk[pc] == 0x90:
            refs.append((pc, word(chunk, pc + 1)))
    return refs


def local_context(data: bytes, decoded, thunks, bank: int, center: int, radius: int = 0x40):
    lines = []
    for pc in decoded_starts(decoded, bank):
        if max(0, center - radius) <= pc < min(0x10000, center + radius):
            mark = " >>>" if pc == center else ""
            lines.append(f"{bank}:{pc:04X}  {fmt_insn(data, bank, pc, thunks)}{mark}")
    return lines


def cluster_primary(seeds: list[Seed], span: int = 0x120):
    out = []
    by_bank: dict[int, list[Seed]] = {}
    for s in seeds:
        by_bank.setdefault(s.bank, []).append(s)
    for bank, rows in by_bank.items():
        rows.sort(key=lambda s: s.pc)
        cur = []
        end = -1
        for s in rows:
            if not cur or s.pc <= end:
                cur.append(s)
                end = max(end, s.pc + span)
            else:
                out.append(cur)
                cur = [s]
                end = s.pc + span
        if cur:
            out.append(cur)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("firmware", type=Path)
    ap.add_argument("--top", type=int, default=12, help="number of ranked candidate clusters to print")
    args = ap.parse_args()

    data = args.firmware.read_bytes()
    if len(data) != 0xE0000 or hashlib.sha256(data).hexdigest() != SHA:
        raise SystemExit("Refusing an image other than verified ASUS V020")

    thunks = inventory(data)
    decoded, *_ = traverse(data, thunks)
    decoded_set = set(decoded)

    primary: list[Seed] = []
    guards: list[Seed] = []

    for bank in range(14):
        chunk = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
        starts = decoded_starts(decoded, bank)
        for idx, pc in enumerate(starts):
            op = chunk[pc]

            if op == 0x90:
                addr = word(chunk, pc + 1)
                if SCRATCH_LO <= addr <= SCRATCH_HI:
                    accesses = scratch_access(data, decoded_set, bank, pc)
                    kinds = ",".join(f"{k}:{a:04X}" for _, a, k in accesses) or "base-only"
                    # D838..D83B are the known unsigned numeric input; writes there matter most.
                    w = 7 if any(k == "WRITE" and 0xD838 <= a <= 0xD83B for _, a, k in accesses) else 4
                    primary.append(Seed(bank, pc, "OSD_SCRATCH", f"{addr:04X} {kinds}", w))

            if op in (0x02, 0x12) and word(chunk, pc + 1) == RENDER_THUNK:
                primary.append(Seed(bank, pc, "NUM_RENDER", f"{'LCALL' if op == 0x12 else 'LJMP'} 1670", 10))

            if op == 0x84:  # DIV AB
                bimm = b_immediate_before_div(chunk, starts, idx)
                if bimm and bimm[1] in (10, 100):
                    primary.append(Seed(bank, pc, "DECIMAL_DIV", f"B={bimm[1]} set at {bimm[0]:04X}", 6))

            gv = guard_value(chunk, pc)
            if gv is not None:
                guards.append(Seed(bank, pc, "GUARD_100", f"immediate {gv}", 2))

    # Known numeric-renderer body is already understood and is not itself a SOC candidate.
    primary = [s for s in primary if not (s.bank == KNOWN_RENDERER_BANK and KNOWN_RENDERER_LO <= s.pc < KNOWN_RENDERER_HI)]

    clusters = []
    for rows in cluster_primary(primary):
        bank = rows[0].bank
        lo = min(s.pc for s in rows)
        hi = max(s.pc for s in rows)
        local_guards = [g for g in guards if g.bank == bank and lo - 0x80 <= g.pc <= hi + 0x80]
        score = sum(s.weight for s in rows) + sum(g.weight for g in local_guards)
        kinds = sorted({s.kind for s in rows})
        # Reward mixed evidence, not repeated accesses alone.
        if len(kinds) >= 2:
            score += 5
        if "NUM_RENDER" in kinds and "OSD_SCRATCH" in kinds:
            score += 6
        if "DECIMAL_DIV" in kinds and "OSD_SCRATCH" in kinds:
            score += 4
        clusters.append((score, bank, lo, hi, rows, local_guards))

    clusters.sort(key=lambda x: (-x[0], x[1], x[2]))

    print("ASUS MB16AMT V020 — SOC/OSD candidate trace")
    print(f"SHA256: {SHA}")
    print("READ-ONLY OFFLINE ANALYSIS; NO DEVICE I/O")
    print("Scope: displayed battery percentage only; VCP ED / D9FF charge-policy path intentionally excluded")
    print()
    print("===== SIGNAL COUNTS =====")
    for kind in ("NUM_RENDER", "OSD_SCRATCH", "DECIMAL_DIV"):
        print(f"{kind}: {sum(1 for s in primary if s.kind == kind)}")
    print(f"nearby 99/100/101 guards catalogued: {len(guards)}")
    print()

    print("===== EXACT DIRECT CALLERS OF CONFIRMED NUMERIC RENDERER 1670 =====")
    render_calls = [s for s in primary if s.kind == "NUM_RENDER"]
    if not render_calls:
        print("(none outside known renderer body)")
    for s in render_calls:
        print(f"{s.bank}:{s.pc:04X}  {s.detail}")
    print()

    print("===== RANKED SOC/OSD CANDIDATE CLUSTERS =====")
    if not clusters:
        print("(no candidates)")
        return 0

    for rank, item in enumerate(clusters[:max(1, args.top)], 1):
        score, bank, lo, hi, rows, local_guards = item
        center = max(rows, key=lambda s: s.weight).pc
        print()
        print(f"### #{rank} score={score} bank={bank} span={lo:04X}-{hi:04X} center={center:04X}")
        for s in rows:
            print(f"  {s.bank}:{s.pc:04X} {s.kind:<11} +{s.weight}  {s.detail}")
        for g in local_guards:
            print(f"  {g.bank}:{g.pc:04X} {g.kind:<11} +{g.weight}  {g.detail}")

        refs = nearby_xdata_refs(data, decoded, bank, max(0, lo - 0x60), min(0x10000, hi + 0xA0))
        unique = []
        seen = set()
        for pc, addr in refs:
            if addr not in seen:
                seen.add(addr)
                unique.append((pc, addr))
        if unique:
            print("  XDATA refs nearby:")
            for pc, addr in unique[:24]:
                tag = " [OSD scratch]" if SCRATCH_LO <= addr <= SCRATCH_HI else ""
                print(f"    {bank}:{pc:04X} -> {addr:04X}{tag}")

        print("  Context:")
        for line in local_context(data, decoded, thunks, bank, center):
            print("    " + line)

    print()
    print("===== INTERPRETATION RULE =====")
    print("Promote a SOC candidate only when a 0..100 value is proven to flow into an OSD numeric/digit path.")
    print("Then trace that value backward to its XDATA/RAM producer; do not infer SOC from charge-policy state.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

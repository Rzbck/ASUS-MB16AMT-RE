"""Focused static audit of the bank-12 DDC/CI-looking region in ASUS V020.

Read-only/offline. The generic ADD A,#ED ranking mixed several neighboring
functions. This tool isolates bank 12 around EF40..F140, inventories exact
callers of the candidate helper entries, traces D9C0/D991/D997-family XDATA
references, and dumps the MOVC table neighborhoods. It does not name a function
as DDC until data-flow proves it.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib

from analyze_banked_abi import BANK_SIZE, LENGTHS, SHA, inventory, traverse, word
from mcs51 import decode

BANK = 12
REGION_LO = 0xEF40
REGION_HI = 0xF140
TARGETS = [0xEFF2, 0xF0B7, 0xF0C5, 0xF0E7, 0xF109, 0xFDEC, 0xFDE5, 0xFDFA]
XDATA_TARGETS = {0xD9C0, 0xD991, 0xD993, 0xD996, 0xD997, 0xD998, 0xD832}
TABLE_SITES = [0xF0DC, 0xF0E0, 0xF0E4]


def insn_text(data: bytes, pc: int) -> str:
    chunk = data[BANK * BANK_SIZE:(BANK + 1) * BANK_SIZE]
    try:
        return decode(chunk, pc)
    except Exception as exc:
        return f"<decode error {exc}>"


def decoded_callers(data: bytes, decoded, thunks, target_pc: int):
    rows = []
    for (bank, pc), _size in sorted(decoded.items()):
        p = bank * BANK_SIZE + pc
        op = data[p]
        if bank == BANK and op in (0x02, 0x12) and word(data, p + 1) == target_pc:
            rows.append((bank, pc, "LJMP" if op == 0x02 else "LCALL", None))
        if op in (0x02, 0x12):
            raw = word(data, p + 1)
            if raw in thunks and thunks[raw] == (BANK, target_pc):
                rows.append((bank, pc, "LJMP-thunk" if op == 0x02 else "LCALL-thunk", raw))
    return rows


def xdata_refs(data: bytes, decoded):
    rows = []
    for (bank, pc), _size in sorted(decoded.items()):
        if bank != BANK:
            continue
        p = bank * BANK_SIZE + pc
        if data[p] != 0x90:
            continue
        addr = word(data, p + 1)
        if addr in XDATA_TARGETS:
            rows.append((pc, addr))
    return rows


def local_decoded_listing(data: bytes, decoded, lo: int, hi: int):
    lines = []
    chunk = data[BANK * BANK_SIZE:(BANK + 1) * BANK_SIZE]
    for pc in sorted(p for (b, p) in decoded if b == BANK and lo <= p < hi):
        txt = insn_text(data, pc)
        if chunk[pc] in (0x02, 0x12):
            lines.append((pc, txt, word(chunk, pc + 1)))
        else:
            lines.append((pc, txt, None))
    return lines


def hex_dump(data: bytes, lo: int, hi: int) -> str:
    chunk = data[BANK * BANK_SIZE:(BANK + 1) * BANK_SIZE]
    out = []
    for base in range(lo, hi, 16):
        part = chunk[base:min(base + 16, hi)]
        out.append(f"{BANK}:{base:04X}  " + " ".join(f"{b:02X}" for b in part))
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("firmware", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    data = args.firmware.read_bytes()
    if len(data) != 0xE0000 or hashlib.sha256(data).hexdigest() != SHA:
        raise SystemExit("Refusing an image other than verified ASUS V020")

    thunks = inventory(data)
    decoded, *_ = traverse(data, thunks)
    args.out.mkdir(parents=True, exist_ok=True)

    lines = [
        "ASUS MB16AMT V020 — focused bank12 DDC candidate audit",
        f"SHA256: {SHA}",
        "READ-ONLY OFFLINE ANALYSIS; NO DEVICE I/O",
        "",
        f"===== DECODED REGION {BANK}:{REGION_LO:04X}-{REGION_HI:04X} =====",
    ]

    chunk = data[BANK * BANK_SIZE:(BANK + 1) * BANK_SIZE]
    for pc, txt, raw_target in local_decoded_listing(data, decoded, REGION_LO, REGION_HI):
        suffix = ""
        if raw_target is not None:
            if raw_target in thunks:
                b, a = thunks[raw_target]
                suffix = f" ; -> {b}:{a:04X}"
            else:
                suffix = f" ; local/raw target {raw_target:04X}"
        mark = "  <<< ADD A,#ED" if pc == 0xEFF8 else ""
        lines.append(f"{BANK}:{pc:04X}  {txt}{suffix}{mark}")

    lines += ["", "===== EXACT CALLERS OF CANDIDATE ENTRIES ====="]
    for target in TARGETS:
        callers = decoded_callers(data, decoded, thunks, target)
        lines.append(f"-- {BANK}:{target:04X}: {len(callers)} decoded callers --")
        for b, pc, kind, thunk in callers:
            if thunk is None:
                lines.append(f"{b}:{pc:04X} {kind} -> {BANK}:{target:04X}")
            else:
                lines.append(f"{b}:{pc:04X} {kind} {thunk:04X} -> {BANK}:{target:04X}")

    lines += ["", "===== D9C0 / RX-LIKE XDATA REFERENCES IN BANK 12 ====="]
    refs = xdata_refs(data, decoded)
    for pc, addr in refs:
        lines.append(f"{BANK}:{pc:04X} MOV DPTR,#{addr:04X}")
        nearby = [p for (b, p) in decoded if b == BANK and max(0, pc - 0x18) <= p < min(BANK_SIZE, pc + 0x28)]
        for p in sorted(nearby):
            marker = " >>>" if p == pc else ""
            lines.append(f"  {BANK}:{p:04X} {insn_text(data, p)}{marker}")
        lines.append("")

    lines += ["", "===== D9C0=6E STATIC ASSERTIONS ====="]
    d9c0_sites = []
    for pc, addr in refs:
        if addr != 0xD9C0:
            continue
        d9c0_sites.append(pc)
        following = []
        cur = pc + LENGTHS[chunk[pc]]
        for _ in range(6):
            if (BANK, cur) not in decoded:
                break
            following.append(f"{cur:04X}:{insn_text(data, cur)}")
            cur += LENGTHS[chunk[cur]]
        lines.append(f"{BANK}:{pc:04X} -> " + " | ".join(following))
    lines.append(f"D9C0 direct loads found in bank12: {len(d9c0_sites)}")

    lines += ["", "===== MOVC TABLE NEIGHBORHOODS ====="]
    for site in TABLE_SITES:
        lines.append(f"-- around {BANK}:{site:04X} --")
        lines.append(hex_dump(data, max(REGION_LO, site - 0x30), min(REGION_HI, site + 0x40)))

    lines += ["", "===== FOCUSED BYTES AROUND EFF2 =====", hex_dump(data, 0xEFE0, 0xF030)]

    lines += [
        "",
        "Interpretation constraints:",
        "- D9C0=0x6E is strong DDC-neighborhood evidence because public RL6492 source defines _DDCCI_DEST_ADDRESS as 0x6E.",
        "- It does not by itself prove EFF2/EFF8 belongs to the same function.",
        "- Promote R5 to 'VCP source opcode' only if callers/data-flow establish that provenance.",
    ]

    out = args.out / "bank12-ddc-focused.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Report written: {out}")
    print(f"D9C0 direct loads in bank12: {len(d9c0_sites)}")
    for target in TARGETS:
        print(f"{BANK}:{target:04X} callers={len(decoded_callers(data, decoded, thunks, target))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

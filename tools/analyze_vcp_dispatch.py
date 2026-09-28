"""Find decoded VCP 0xED dispatcher candidates in the verified V020 image.

This is a static/offline heuristic. It searches only instruction-boundary-aware
code recovered by the existing ABI/CFG analyzer and reports immediate constants;
it does not treat arbitrary byte 0xED occurrences as evidence.

The goal is to find the ASUS DDC/VCP switch region that handles the already
runtime-proven charge-policy feature ED, then trace its callees toward internal
power/charging state.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import csv
import hashlib
import json

from analyze_banked_abi import BANK_SIZE, LENGTHS, SHA, inventory, traverse, word

# High/vendor-ish VCP codes advertised by the MB16AMT capability string. Keeping
# the low/common values out of the score dramatically reduces generic constants.
VENDOR_VCPS = {
    0xAA, 0xAC, 0xAE, 0xB2, 0xB6, 0xC6, 0xC8, 0xCC,
    0xD6, 0xDC, 0xDF, 0xE0, 0xE3, 0xE4, 0xE9, 0xEB,
    0xED, 0xF0, 0xF1, 0xFD, 0xFF,
}

# Opcodes where one operand is genuinely an immediate 8-bit value. Direct/XDATA
# addresses and branch displacements are intentionally excluded.
IMM_AT_1 = {
    0x24: "ADD A,#imm",
    0x34: "ADDC A,#imm",
    0x44: "ORL A,#imm",
    0x54: "ANL A,#imm",
    0x64: "XRL A,#imm",
    0x74: "MOV A,#imm",
    0x76: "MOV @R0,#imm",
    0x77: "MOV @R1,#imm",
    0x94: "SUBB A,#imm",
    0xB4: "CJNE A,#imm,rel",
    0xB6: "CJNE @R0,#imm,rel",
    0xB7: "CJNE @R1,#imm,rel",
    **{op: f"MOV R{op - 0x78},#imm" for op in range(0x78, 0x80)},
    **{op: f"CJNE R{op - 0xB8},#imm,rel" for op in range(0xB8, 0xC0)},
}

IMM_AT_2 = {
    0x43: "ORL direct,#imm",
    0x53: "ANL direct,#imm",
    0x63: "XRL direct,#imm",
    0x75: "MOV direct,#imm",
}


def decoded_immediates(data: bytes, decoded: dict[tuple[int, int], int]):
    rows = []
    for (bank, pc), size in sorted(decoded.items()):
        p = bank * BANK_SIZE + pc
        op = data[p]
        if op in IMM_AT_1 and size >= 2:
            rows.append((bank, pc, op, data[p + 1], IMM_AT_1[op]))
        elif op in IMM_AT_2 and size >= 3:
            rows.append((bank, pc, op, data[p + 2], IMM_AT_2[op]))
    return rows


def nearby_calls(data: bytes, decoded: dict[tuple[int, int], int], thunks, bank: int, center: int, radius: int = 0x80):
    out = []
    lo, hi = max(0, center - radius), min(BANK_SIZE, center + radius + 1)
    for pc in range(lo, hi):
        if (bank, pc) not in decoded:
            continue
        p = bank * BANK_SIZE + pc
        op = data[p]
        if op == 0x12:  # LCALL addr16
            target = word(data, p + 1)
            if target in thunks:
                db, da = thunks[target]
                out.append(f"{pc:04X}:LCALL {target:04X}->{db}:{da:04X}")
            else:
                out.append(f"{pc:04X}:LCALL {bank}:{target:04X}")
        elif op & 0x1F == 0x11:  # ACALL
            nxt = (pc + LENGTHS[op]) & 0xFFFF
            target = (nxt & 0xF800) | ((op & 0xE0) << 3) | data[p + 1]
            out.append(f"{pc:04X}:ACALL {bank}:{target:04X}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("firmware", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--radius", type=lambda x: int(x, 0), default=0x300,
                    help="same-bank literal clustering radius (default 0x300)")
    args = ap.parse_args()

    data = args.firmware.read_bytes()
    if len(data) != 0xE0000 or hashlib.sha256(data).hexdigest() != SHA:
        raise SystemExit("Refusing an image other than verified ASUS V020")

    thunks = inventory(data)
    decoded, edges, indirect, reserved, overlaps = traverse(data, thunks)
    immediates = decoded_immediates(data, decoded)
    vendor = [(b, pc, op, value, text) for b, pc, op, value, text in immediates if value in VENDOR_VCPS]
    ed_uses = [row for row in vendor if row[3] == 0xED]

    args.out.mkdir(parents=True, exist_ok=True)

    ed_rows = []
    for bank, pc, op, value, text in ed_uses:
        near = [r for r in vendor if r[0] == bank and abs(r[1] - pc) <= args.radius]
        values = sorted({r[3] for r in near})
        calls = nearby_calls(data, decoded, thunks, bank, pc)
        ed_rows.append((
            bank,
            f"{pc:04X}",
            f"{op:02X}",
            text,
            len(near),
            " ".join(f"{v:02X}" for v in values),
            " | ".join(calls),
        ))

    with (args.out / "vcp-ed-uses.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["physical_bank", "site", "opcode", "instruction", "nearby_vendor_immediates",
                    "distinct_vendor_vcps", "nearby_calls_0x80"])
        w.writerows(ed_rows)

    all_rows = [(b, f"{pc:04X}", f"{op:02X}", text, f"{value:02X}")
                for b, pc, op, value, text in vendor]
    with (args.out / "vcp-vendor-immediates.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["physical_bank", "site", "opcode", "instruction", "immediate"])
        w.writerows(all_rows)

    ranked = sorted(ed_rows, key=lambda r: (-len(r[5].split()), -r[4], r[0], r[1]))
    summary = {
        "sha256": SHA,
        "method": "CFG-boundary decoded 8-bit immediate literals only; raw 0xED bytes ignored",
        "vendor_vcp_literal_uses": len(vendor),
        "decoded_ed_uses": len(ed_uses),
        "cluster_radius": args.radius,
        "ranked_ed_candidates": [
            {
                "physical_bank": r[0],
                "site": r[1],
                "instruction": r[3],
                "nearby_vendor_immediates": r[4],
                "distinct_vendor_vcps": r[5].split(),
                "nearby_calls_0x80": r[6].split(" | ") if r[6] else [],
            }
            for r in ranked
        ],
        "limits": (
            "Heuristic only. A compiler may implement the VCP switch through tables, direct-address loads, "
            "or indirect dispatch that does not contain immediate ED at a CFG-reached instruction. "
            "Candidates require manual control-flow/data-flow confirmation before assigning semantics."
        ),
    }
    (args.out / "vcp-ed-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

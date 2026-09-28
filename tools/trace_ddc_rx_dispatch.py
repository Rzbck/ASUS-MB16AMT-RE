"""Trace the inferred DDC/CI RX buffer command/opcode fields in ASUS MB16AMT V020.

Read-only/offline. Strong static evidence identifies D9C0 as the DDC TX buffer
base and D990 as the corresponding RX buffer base:
  RX+2 D992 = command byte (public Realtek index _DDCCI_COMMAND)
  RX+3 D993 = source/VCP opcode (public index _DDCCI_SOURCE_OPCODE)

This tool inventories decoded direct references to D992/D993 across all logical
file banks, highlights tests of command 0x03 (Set VCP Feature), and prints compact
instruction contexts for every direct D993 read so the real VCP dispatcher can be
located without searching for literal 0xED bytes.

It performs no device I/O.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib

from analyze_banked_abi import BANK_SIZE, LENGTHS, SHA, inventory, traverse, word
from mcs51 import decode

RX_BASE = 0xD990
RX_COMMAND = RX_BASE + 2   # D992
RX_OPCODE = RX_BASE + 3    # D993
TX_BASE = 0xD9C0


def insn(data: bytes, bank: int, pc: int) -> str:
    chunk = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    try:
        return decode(chunk, pc)
    except Exception as exc:
        return f"<decode error {exc}>"


def branch_target(data: bytes, bank: int, pc: int):
    chunk = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    op = chunk[pc]
    n = LENGTHS[op]
    if op in (0x40, 0x50, 0x60, 0x70, 0x80):
        v = chunk[pc + 1]
        if v >= 0x80:
            v -= 0x100
        return (pc + n + v) & 0xFFFF
    if op in (0x10, 0x20, 0x30) or 0xB4 <= op <= 0xBF or op == 0xD5:
        v = chunk[pc + n - 1]
        if v >= 0x80:
            v -= 0x100
        return (pc + n + v) & 0xFFFF
    if 0xD8 <= op <= 0xDF:
        v = chunk[pc + 1]
        if v >= 0x80:
            v -= 0x100
        return (pc + n + v) & 0xFFFF
    return None


def local_context(data: bytes, decoded, bank: int, center: int, before=8, after=18):
    starts = sorted(pc for (b, pc) in decoded if b == bank)
    try:
        idx = starts.index(center)
    except ValueError:
        return []
    lo = max(0, idx - before)
    hi = min(len(starts), idx + after + 1)
    out = []
    for pc in starts[lo:hi]:
        mark = " >>>" if pc == center else ""
        out.append(f"{bank}:{pc:04X}  {insn(data, bank, pc)}{mark}")
    return out


def direct_dptr_refs(data: bytes, decoded, addr: int):
    rows = []
    for (bank, pc) in sorted(decoded):
        p = bank * BANK_SIZE + pc
        if data[p] == 0x90 and word(data, p + 1) == addr:
            rows.append((bank, pc))
    return rows


def immediate_after_read(data: bytes, decoded, bank: int, dptr_pc: int, limit=18):
    """Describe straight-line operations after MOV DPTR,#field / MOVX A,@DPTR.

    Conservative: stop on calls, returns, unconditional jumps or a second DPTR
    load. Conditional branches are included and then stop because path splits.
    """
    chunk = data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
    pcs = sorted(pc for (b, pc) in decoded if b == bank and pc >= dptr_pc)
    try:
        i = pcs.index(dptr_pc)
    except ValueError:
        return []
    out = []
    for pc in pcs[i:i + limit]:
        op = chunk[pc]
        out.append((pc, insn(data, bank, pc), branch_target(data, bank, pc)))
        if pc != dptr_pc and op == 0x90:
            break
        if op in (0x02, 0x12, 0x22, 0x32, 0x73, 0x80) or op & 0x1F in (0x01, 0x11):
            break
        if op in (0x40, 0x50, 0x60, 0x70, 0x10, 0x20, 0x30, 0xD5) or 0xB4 <= op <= 0xBF or 0xD8 <= op <= 0xDF:
            break
    return out


def command03_sites(data: bytes, decoded):
    """Find direct D992 reads followed locally by an exact compare/test for 0x03."""
    rows = []
    chunk_cache = {}
    for bank, pc in direct_dptr_refs(data, decoded, RX_COMMAND):
        chunk = chunk_cache.setdefault(bank, data[bank * BANK_SIZE:(bank + 1) * BANK_SIZE])
        starts = sorted(x for (b, x) in decoded if b == bank and pc <= x < min(BANK_SIZE, pc + 0x30))
        evidence = []
        for q in starts:
            op = chunk[q]
            txt = insn(data, bank, q)
            exact = False
            if op in (0x64, 0x94, 0xB4) and q + 1 < BANK_SIZE and chunk[q + 1] == 0x03:
                exact = True
            if op == 0x24 and q + 1 < BANK_SIZE and chunk[q + 1] == 0xFD:
                # A += -3 is frequently switch normalization around command 3.
                exact = True
            if exact:
                evidence.append((q, txt))
            if q != pc and op == 0x90:
                break
            if op in (0x02, 0x22, 0x32, 0x73, 0x80):
                break
        if evidence:
            rows.append((bank, pc, evidence))
    return rows


def tx_signature_assertions(data: bytes):
    """Return whether the exact bank12 TX-header evidence remains present."""
    base = 12 * BANK_SIZE
    # EF5E: MOV DPTR,#D9C0; MOV A,#6E; MOVX; INC; MOV A,#88; MOVX;
    #       INC; MOV A,#02; MOVX; CLR A; INC; MOVX
    sig = bytes.fromhex("90 D9 C0 74 6E F0 74 88")
    # INC DPTR sits between stores, so use explicit semantic byte checks below.
    c = data[base:base + BANK_SIZE]
    ok_header = (
        c[0xEF5E:0xEF61] == bytes.fromhex("90 D9 C0") and
        c[0xEF61:0xEF64] == bytes.fromhex("74 6E F0") and
        c[0xEF64:0xEF69] == bytes.fromhex("74 88 A3 F0 A3") and
        c[0xEF69:0xEF6C] == bytes.fromhex("74 02 F0")
    )
    ok_copy = (
        c[0xEFB1:0xEFB4] == bytes.fromhex("90 D9 93") and
        c[0xEFB4] == 0xE0 and
        c[0xEFB5:0xEFB8] == bytes.fromhex("90 D9 C4") and
        c[0xEFB8] == 0xF0
    )
    return ok_header, ok_copy


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("firmware", type=Path)
    ap.add_argument("--out", type=Path, default=None,
                    help="optional report file; report is always printed to stdout")
    args = ap.parse_args()

    data = args.firmware.read_bytes()
    if len(data) != 0xE0000 or hashlib.sha256(data).hexdigest() != SHA:
        raise SystemExit("Refusing an image other than verified ASUS V020")

    thunks = inventory(data)
    decoded, *_ = traverse(data, thunks)
    cmd_refs = direct_dptr_refs(data, decoded, RX_COMMAND)
    op_refs = direct_dptr_refs(data, decoded, RX_OPCODE)
    cmd03 = command03_sites(data, decoded)
    ok_header, ok_copy = tx_signature_assertions(data)

    lines = []
    emit = lambda s="": lines.append(str(s))
    emit("ASUS MB16AMT V020 — DDC RX dispatch trace")
    emit(f"SHA256: {SHA}")
    emit("READ-ONLY OFFLINE ANALYSIS; NO DEVICE I/O")
    emit()
    emit("===== BUFFER IDENTITY EVIDENCE =====")
    emit(f"bank12 EF5E D9C0 Get-VCP-reply header signature: {'PASS' if ok_header else 'FAIL'}")
    emit(f"bank12 EFB1 D993 -> D9C4 opcode echo signature: {'PASS' if ok_copy else 'FAIL'}")
    emit("Public-structure hypothesis used for tracing: D990=RxBuf base, D992=command, D993=source/VCP opcode, D9C0=TxBuf base")
    emit()
    emit("===== GLOBAL DIRECT REFERENCE COUNTS =====")
    emit(f"D992 command refs: {len(cmd_refs)}")
    emit(f"D993 opcode refs:  {len(op_refs)}")
    emit()
    emit("===== D992 SITES THAT TEST SET-VCP COMMAND 0x03 =====")
    if not cmd03:
        emit("(none found by conservative direct-DPTR pattern)")
    for bank, pc, ev in cmd03:
        emit(f"-- {bank}:{pc:04X} MOV DPTR,#D992 --")
        for q, txt in ev:
            emit(f"  evidence {bank}:{q:04X} {txt}")
        for row in local_context(data, decoded, bank, pc, before=6, after=18):
            emit("  " + row)
        emit()

    emit("===== ALL DIRECT D993 (VCP OPCODE) READ/USE SITES =====")
    for bank, pc in op_refs:
        emit(f"-- {bank}:{pc:04X} MOV DPTR,#D993 --")
        seq = immediate_after_read(data, decoded, bank, pc, limit=20)
        if not seq:
            emit("  (no decoded straight-line sequence)")
        for q, txt, tgt in seq:
            suffix = f" -> {bank}:{tgt:04X}" if tgt is not None else ""
            emit(f"  {bank}:{q:04X} {txt}{suffix}")
        emit()

    emit("===== PRIORITY RULE =====")
    emit("Look for a D993 read whose value is dispatched/compared in the control-flow reached after a D992==03 Set-VCP test.")
    emit("Only after that provenance is proven should an ED branch be labeled VCP ED.")

    text = "\n".join(lines) + "\n"
    print(text, end="")
    if args.out is not None:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "ddc-rx-dispatch.txt").write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

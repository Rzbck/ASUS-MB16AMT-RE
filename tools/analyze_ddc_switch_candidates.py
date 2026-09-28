"""Rank the six V020 ADD A,#ED regions as possible compiled DDC/VCP switches.

Read-only/offline. Earlier scanning found six instruction-boundary-aware
`ADD A,#0xED` sites. Because 0xED == -0x13 modulo 256, these may be switch-index
normalization sequences rather than literal VCP values. This tool inspects their
local data-flow shape, XDATA inputs, table-dispatch instructions and outgoing
calls without assigning semantics automatically.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib
import json

from analyze_banked_abi import BANK_SIZE, LENGTHS, SHA, inventory, traverse, word
from mcs51 import decode

CANDIDATES = [
    (12, 0xEFF8),
    (5, 0xD80F),
    (1, 0xE7FD),
    (6, 0xDE3B),
    (4, 0xF1E2),
    (4, 0xF2A2),
]

# Advertised/common high VCPs useful only as local cluster evidence.
VENDORISH = {
    0xAA, 0xAC, 0xAE, 0xB2, 0xB6, 0xC6, 0xC8, 0xCC,
    0xD6, 0xDC, 0xDF, 0xE0, 0xE3, 0xE4, 0xE9, 0xEB,
    0xED, 0xF0, 0xF1, 0xFD, 0xFF,
}

IMM1 = set([0x24,0x34,0x44,0x54,0x64,0x74,0x76,0x77,0x94,0xB4,0xB6,0xB7]) | set(range(0x78,0x80)) | set(range(0xB8,0xC0))
IMM2 = {0x43,0x53,0x63,0x75}


def decoded_window(decoded, bank, center, before, after):
    return sorted(pc for (b, pc) in decoded if b == bank and center-before <= pc < center+after)


def text_at(data, bank, pc):
    chunk = data[bank*BANK_SIZE:(bank+1)*BANK_SIZE]
    try:
        return decode(chunk, pc)
    except Exception as e:
        return f"<decode error {e}>"


def call_target(data, thunks, bank, pc):
    p = bank*BANK_SIZE + pc
    op = data[p]
    if op == 0x12:
        t = word(data, p+1)
        if t in thunks:
            b,a = thunks[t]
            return f"LCALL {t:04X}->{b}:{a:04X}"
        return f"LCALL {bank}:{t:04X}"
    if op == 0x02:
        t = word(data, p+1)
        if t in thunks:
            b,a = thunks[t]
            return f"LJMP {t:04X}->{b}:{a:04X}"
        return f"LJMP {bank}:{t:04X}"
    if op & 0x1F == 0x11:
        n = (pc + LENGTHS[op]) & 0xFFFF
        t = (n & 0xF800) | ((op & 0xE0)<<3) | data[p+1]
        return f"ACALL {bank}:{t:04X}"
    return None


def immediate_value(data, bank, pc):
    p = bank*BANK_SIZE + pc
    op = data[p]
    if op in IMM1:
        return data[p+1]
    if op in IMM2:
        return data[p+2]
    return None


def nearest_accumulator_source(data, decoded, bank, center, limit=0x50):
    """Conservative local backtrace: return notable instructions before ADD A,#ED.

    This is descriptive, not SSA. It stops at obvious control-flow boundaries.
    """
    starts = [pc for (b,pc) in decoded if b == bank and max(0, center-limit) <= pc < center]
    starts.sort(reverse=True)
    rows=[]
    for pc in starts:
        p = bank*BANK_SIZE + pc
        op = data[p]
        txt = text_at(data,bank,pc)
        rows.append((pc,txt))
        if op in (0x02,0x22,0x32,0x73,0x80) or op & 0x1F == 0x01:
            break
        # A strong load/source candidate is useful even if we continue a few rows.
        if op in (0xE0,0xE2,0xE3,0xE5,0xE6,0xE7,0xE8,0xE9,0xEA,0xEB,0xEC,0xED,0xEE,0xEF,0x74,0x83,0x93):
            if len(rows) >= 8:
                break
    return list(reversed(rows))


def dptr_xdata_refs(data, decoded, bank, lo, hi):
    refs=[]
    for pc in sorted(pc for (b,pc) in decoded if b == bank and lo <= pc < hi):
        p=bank*BANK_SIZE+pc
        if data[p] != 0x90:
            continue
        addr=word(data,p+1)
        if addr < 0x8000:
            continue
        nxt=pc+3
        next_txt = text_at(data,bank,nxt) if (bank,nxt) in decoded else ""
        refs.append((pc,addr,next_txt))
    return refs


def analyze_one(data, decoded, thunks, bank, center, radius):
    pcs=decoded_window(decoded,bank,center,radius,radius)
    chunk=data[bank*BANK_SIZE:(bank+1)*BANK_SIZE]
    vendor=[]
    calls=[]
    table_ops=[]
    for pc in pcs:
        op=chunk[pc]
        imm=immediate_value(data,bank,pc)
        if imm in VENDORISH:
            vendor.append((pc,imm,text_at(data,bank,pc)))
        ct=call_target(data,thunks,bank,pc)
        if ct:
            calls.append((pc,ct))
        if op in (0x73,0x83,0x93):
            table_ops.append((pc,text_at(data,bank,pc)))
        if op == 0x12 and word(data,bank*BANK_SIZE+pc+1) in (0x210D,0x20D0):
            table_ops.append((pc,ct or text_at(data,bank,pc)))

    refs=dptr_xdata_refs(data,decoded,bank,max(0,center-radius),min(BANK_SIZE,center+radius))
    back=nearest_accumulator_source(data,decoded,bank,center)

    score=0
    score += min(len({v for _,v,_ in vendor}), 10)
    score += 4*len(table_ops)
    # XDATA load immediately before arithmetic normalization is a useful sign.
    if any("MOVX A,@DPTR" in t for _,t in back):
        score += 5
    # Switch-like compare density.
    compare_count=sum(1 for pc in pcs if 0xB4 <= chunk[pc] <= 0xBF)
    score += min(compare_count,6)

    return {
        "bank":bank,
        "site":f"{center:04X}",
        "score":score,
        "distinct_vendor_values":[f"{v:02X}" for v in sorted({v for _,v,_ in vendor})],
        "vendor_literals":[f"{pc:04X}:{v:02X}:{txt}" for pc,v,txt in vendor],
        "table_dispatch_ops":[f"{pc:04X}:{txt}" for pc,txt in table_ops],
        "nearby_calls":[f"{pc:04X}:{txt}" for pc,txt in calls],
        "xdata_refs":[f"{pc:04X}->{addr:04X} next={nxt}" for pc,addr,nxt in refs],
        "backtrace_into_add_ed":[f"{pc:04X}:{txt}" for pc,txt in back],
        "compare_count":compare_count,
    }


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("firmware",type=Path)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--radius",type=lambda x:int(x,0),default=0x100)
    args=ap.parse_args()

    data=args.firmware.read_bytes()
    if len(data)!=0xE0000 or hashlib.sha256(data).hexdigest()!=SHA:
        raise SystemExit("Refusing an image other than verified ASUS V020")

    thunks=inventory(data)
    decoded,*_=traverse(data,thunks)
    rows=[analyze_one(data,decoded,thunks,b,p,args.radius) for b,p in CANDIDATES]
    ranked=sorted(rows,key=lambda r:(-r["score"],r["bank"],r["site"]))
    args.out.mkdir(parents=True,exist_ok=True)

    summary={
        "sha256":SHA,
        "method":"local instruction-boundary-aware ranking of the six ADD A,#ED sites; heuristic only",
        "radius":args.radius,
        "ranked_candidates":ranked,
        "limits":"Scores are triage only. Exact DDC semantics require proving the source opcode byte and handler effects.",
    }
    (args.out/"ddc-switch-candidates.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")

    lines=[
        "ASUS MB16AMT V020 — DDC switch candidate triage",
        f"SHA256: {SHA}",
        "READ-ONLY OFFLINE ANALYSIS; NO DEVICE I/O",
        "",
    ]
    for r in ranked:
        lines += [
            f"===== {r['bank']}:{r['site']} score={r['score']} =====",
            "vendor values: " + " ".join(r['distinct_vendor_values']),
            f"compare count: {r['compare_count']}",
            "-- backtrace into ADD A,#ED --",
            *(r['backtrace_into_add_ed'] or ["(none)"]),
            "-- table/dispatch ops --",
            *(r['table_dispatch_ops'] or ["(none)"]),
            "-- XDATA refs --",
            *(r['xdata_refs'] or ["(none)"]),
            "-- nearby calls --",
            *(r['nearby_calls'] or ["(none)"]),
            "",
        ]
    report=args.out/"ddc-switch-candidates.txt"
    report.write_text("\n".join(lines)+"\n",encoding="utf-8")

    print("Candidate ranking:")
    for r in ranked:
        print(f"  {r['bank']}:{r['site']} score={r['score']} vendor={' '.join(r['distinct_vendor_values']) or '-'} tables={len(r['table_dispatch_ops'])} xdata={len(r['xdata_refs'])}")
    print(f"Report: {report}")
    return 0


if __name__=="__main__":
    raise SystemExit(main())

"""Deep offline resolver/call-path reconstruction for the ASUS MB16AMT updater.

This is phase 2 of the consolidated SOC reconnaissance campaign. It never loads a
vendor DLL and never talks to the monitor. It reconstructs how vendor code resolves
WinComm read APIs, including helper-based GetProcAddress wrappers that are too far
from the API-name xref for a simple proximity scan.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import json
import struct

TARGETS = (
    "ReadRegEx", "ReadRegsEx", "NativeRead", "ReadReg", "ReadRegs",
    "ReadSysDevice", "ReadWordSysDevice", "ReadMcuReg", "ReadMcuRegs",
    "I2CReadEx", "I2CRead", "DDCCIRead",
)


def u16(d: bytes, o: int) -> int:
    return struct.unpack_from("<H", d, o)[0]


def u32(d: bytes, o: int) -> int:
    return struct.unpack_from("<I", d, o)[0]


def s32(d: bytes, o: int) -> int:
    return struct.unpack_from("<i", d, o)[0]


def cstr(d: bytes, o: int, limit: int = 512) -> str:
    e = d.find(b"\0", o, min(len(d), o + limit))
    if e < 0:
        e = min(len(d), o + limit)
    return d[o:e].decode("ascii", "replace")


@dataclass
class Sec:
    name: str
    va: int
    vsize: int
    raw: int
    rawsize: int
    chars: int

    @property
    def executable(self) -> bool:
        return bool(self.chars & 0x20000000)


@dataclass
class PE:
    path: Path
    data: bytes
    image_base: int
    sections: list[Sec]
    import_rva: int
    export_rva: int

    def rva_to_off(self, rva: int):
        for s in self.sections:
            span = max(s.vsize, s.rawsize)
            if s.va <= rva < s.va + span:
                x = rva - s.va
                if x < s.rawsize:
                    return s.raw + x
        return None

    def off_to_rva(self, off: int):
        for s in self.sections:
            if s.raw <= off < s.raw + s.rawsize:
                return s.va + off - s.raw
        return None

    def va_to_off(self, va: int):
        if va < self.image_base:
            return None
        return self.rva_to_off(va - self.image_base)

    def off_to_va(self, off: int):
        r = self.off_to_rva(off)
        return None if r is None else self.image_base + r

    def exec_ranges(self):
        for s in self.sections:
            if s.executable and s.rawsize:
                yield s, s.raw, min(len(self.data), s.raw + s.rawsize)


def parse_pe(path: Path):
    try:
        d = path.read_bytes()
    except OSError:
        return None
    if len(d) < 0x100 or d[:2] != b"MZ":
        return None
    p = u32(d, 0x3C)
    if p + 0x100 >= len(d) or d[p:p+4] != b"PE\0\0":
        return None
    nsec = u16(d, p + 6)
    optsz = u16(d, p + 20)
    opt = p + 24
    if u16(d, opt) != 0x10B:
        return None
    base = u32(d, opt + 28)
    dd = opt + 96
    export_rva = u32(d, dd)
    import_rva = u32(d, dd + 8)
    sh = opt + optsz
    secs = []
    for i in range(nsec):
        o = sh + i * 40
        if o + 40 > len(d):
            break
        secs.append(Sec(
            d[o:o+8].split(b"\0",1)[0].decode("ascii", "replace"),
            u32(d,o+12), u32(d,o+8), u32(d,o+20), u32(d,o+16), u32(d,o+36)
        ))
    return PE(path, d, base, secs, import_rva, export_rva)


def imports(pe: PE):
    out = []
    if not pe.import_rva:
        return out
    off = pe.rva_to_off(pe.import_rva)
    if off is None:
        return out
    for i in range(4096):
        x = off + 20*i
        if x + 20 > len(pe.data):
            break
        oft, _ts, _fc, nrva, ft = struct.unpack_from("<IIIII", pe.data, x)
        if not any((oft,nrva,ft)):
            break
        noff = pe.rva_to_off(nrva)
        dll = cstr(pe.data, noff) if noff is not None else "?"
        toff = pe.rva_to_off(oft or ft)
        if toff is None:
            continue
        for j in range(8192):
            q = toff + 4*j
            if q + 4 > len(pe.data):
                break
            ent = u32(pe.data,q)
            if not ent:
                break
            iat = ft + 4*j
            if ent & 0x80000000:
                name = f"#{ent & 0xffff}"
            else:
                hn = pe.rva_to_off(ent)
                if hn is None:
                    continue
                name = cstr(pe.data, hn+2)
            out.append((dll,name,iat,pe.image_base+iat))
    return out


def find_all(d: bytes, pat: bytes, a=0, b=None):
    if b is None:
        b = len(d)
    p = a
    while True:
        p = d.find(pat,p,b)
        if p < 0:
            return
        yield p
        p += 1


def ascii_strings(pe: PE, name: str):
    pat = name.encode("ascii") + b"\0"
    for o in find_all(pe.data, pat):
        va = pe.off_to_va(o)
        if va is not None:
            yield o, va


def exec_xrefs(pe: PE, va: int):
    imm = struct.pack("<I",va)
    out = []
    for _s,a,b in pe.exec_ranges():
        for p in find_all(pe.data,b"\x68"+imm,a,b):
            out.append((p,"push-imm32",p))
        for op in range(0xB8,0xC0):
            for p in find_all(pe.data,bytes([op])+imm,a,b):
                out.append((p,f"mov-r{op-0xB8}-imm32",p))
        for p in find_all(pe.data,imm,a,b):
            if not any(abs(p-x[0]) <= 1 for x in out):
                out.append((p,"raw-imm32",max(a,p-1)))
    return sorted(set(out))


def iat_va(pe: PE, name: str):
    return [va for _dll,n,_rva,va in imports(pe) if n == name]


def direct_rel_calls_near(pe: PE, center: int, before=8, after=128):
    d=pe.data
    a=max(0,center-before); b=min(len(d),center+after)
    out=[]
    for p in range(a,b-4):
        if d[p] == 0xE8:
            disp=s32(d,p+1)
            base=pe.off_to_va(p)
            if base is None:
                continue
            target_va=base+5+disp
            target_off=pe.va_to_off(target_va)
            out.append((p,target_va,target_off))
        elif d[p:p+2] == b"\xFF\x15" and p+6 <= len(d):
            out.append((p,u32(d,p+2),None))
    return out


def helper_has_gpa(pe: PE, helper_off: int|None, gpa_vas: list[int], span=0x600):
    if helper_off is None:
        return []
    b=min(len(pe.data),helper_off+span)
    hits=[]
    for gva in gpa_vas:
        pat=b"\xFF\x15"+struct.pack("<I",gva)
        hits.extend(find_all(pe.data,pat,helper_off,b))
    return sorted(set(hits))


def stores_eax_after(pe: PE, call_off: int, call_len: int, span=64):
    d=pe.data; p=call_off+call_len; end=min(len(d),p+span); out=[]
    while p < end:
        if d[p:p+1] == b"\xA3" and p+5 <= len(d):
            out.append((p,"mov [abs],eax",u32(d,p+1))); p+=5; continue
        if d[p:p+2] == b"\x89\x05" and p+6 <= len(d):
            out.append((p,"mov [abs],eax",u32(d,p+2))); p+=6; continue
        if d[p:p+2] == b"\x89\x0D" and p+6 <= len(d):
            out.append((p,"mov [abs],ecx",u32(d,p+2))); p+=6; continue
        if d[p] == 0xE8 or d[p:p+2] == b"\xFF\x15":
            break
        p += 1
    return out


def slot_uses(pe: PE, slot: int):
    imm=struct.pack("<I",slot)
    pats=[
        (b"\xFF\x15"+imm,"call [slot]",6),
        (b"\xFF\x25"+imm,"jmp [slot]",6),
        (b"\xA1"+imm,"mov eax,[slot]",5),
        (b"\x8B\x0D"+imm,"mov ecx,[slot]",6),
        (b"\x8B\x15"+imm,"mov edx,[slot]",6),
        (b"\x8B\x1D"+imm,"mov ebx,[slot]",6),
        (b"\x8B\x35"+imm,"mov esi,[slot]",6),
        (b"\x8B\x3D"+imm,"mov edi,[slot]",6),
    ]
    out=[]
    for _s,a,b in pe.exec_ranges():
        for pat,label,l in pats:
            for p in find_all(pe.data,pat,a,b):
                out.append((p,label,l))
    return sorted(out)


def arg_summary(pe: PE, off: int, before=64):
    d=pe.data; a=max(0,off-before); p=a; out=[]
    while p < off:
        op=d[p]
        if op == 0x68 and p+5 <= off:
            out.append((p,f"push 0x{u32(d,p+1):08X}")); p+=5; continue
        if op == 0x6A and p+2 <= off:
            out.append((p,f"push 0x{d[p+1]:02X}")); p+=2; continue
        if 0x50 <= op <= 0x57:
            out.append((p,f"push reg{op-0x50}")); p+=1; continue
        if 0xB8 <= op <= 0xBF and p+5 <= off:
            out.append((p,f"mov reg{op-0xB8},0x{u32(d,p+1):08X}")); p+=5; continue
        if op == 0x8D:
            out.append((p,"lea ..."))
        p+=1
    return out[-14:]


def hex_context(pe: PE, center: int, before=48, after=80):
    a=max(0,center-before); b=min(len(pe.data),center+after); lines=[]
    for o in range(a,b,16):
        q=pe.data[o:min(b,o+16)]
        hx=" ".join(f"{x:02X}" for x in q)
        asc="".join(chr(x) if 32<=x<127 else "." for x in q)
        mark=" <==" if o <= center < o+16 else ""
        va=pe.off_to_va(o)
        vatxt=("0x%08X"%va) if va is not None else "n/a"
        lines.append(f"file+0x{o:08X} VA={vatxt:>10}  {hx:<47} {asc}{mark}")
    return "\n".join(lines)


def analyze_pe(pe: PE, root: Path):
    gpa_vas=iat_va(pe,"GetProcAddress")
    results=[]
    helper_groups={}
    for name in TARGETS:
        strings=list(ascii_strings(pe,name))
        xrs=[]
        for soff,sva in strings:
            for xo,kind,scan_start in exec_xrefs(pe,sva):
                calls=direct_rel_calls_near(pe,scan_start,4,160)
                call_entries=[]
                for co,tva,to in calls[:12]:
                    gpa_hits=helper_has_gpa(pe,to,gpa_vas) if to is not None else []
                    direct_gpa=tva in gpa_vas
                    stores=stores_eax_after(pe,co,5 if pe.data[co]==0xE8 else 6)
                    uses=[]
                    for st_off,st_kind,slot in stores:
                        uses.extend((slot,)+u for u in slot_uses(pe,slot))
                    call_entries.append({
                        "call_off":co,"target_va":tva,"target_off":to,
                        "direct_gpa":direct_gpa,"helper_gpa_hits":gpa_hits,
                        "stores":stores,"uses":uses,
                    })
                    if to is not None:
                        helper_groups.setdefault(to,set()).add(name)
                xrs.append({"string_off":soff,"string_va":sva,"xref_off":xo,"kind":kind,"calls":call_entries})
        results.append({"name":name,"strings":strings,"xrefs":xrs})

    shared=[]
    for hoff,names in sorted(helper_groups.items()):
        if len(names) < 2:
            continue
        gh=helper_has_gpa(pe,hoff,gpa_vas)
        shared.append({"helper_off":hoff,"helper_va":pe.off_to_va(hoff),"names":sorted(names),"gpa_hits":gh})

    api_verdicts=[]
    for r in results:
        if not r["strings"]:
            continue
        status="DATA_ONLY"; score=10; evidence=[]; slots=[]; uses=[]; helpers=[]
        if r["xrefs"]:
            status="STRONG_CODE_XREF"; score=50
        for xr in r["xrefs"]:
            for ce in xr["calls"]:
                if ce["direct_gpa"]:
                    status="CANDIDATE_DIRECT_RESOLVER"; score=max(score,90); evidence.append((xr["xref_off"],ce["call_off"],"direct GetProcAddress"))
                if ce["helper_gpa_hits"]:
                    status="CANDIDATE_HELPER_RESOLVER"; score=max(score,95); evidence.append((xr["xref_off"],ce["call_off"],"helper calls GetProcAddress")); helpers.append(ce["target_off"])
                slots.extend(ce["stores"])
                uses.extend(ce["uses"])
        if uses and status.startswith("CANDIDATE"):
            status="CANDIDATE_RESOLVER_USED"; score=110
        if r["name"] == "ReadRegEx": score += 20
        elif r["name"] == "ReadRegsEx": score += 18
        elif r["name"] == "NativeRead": score += 15
        if r["name"] in {"ReadMcuReg","ReadMcuRegs"}: score -= 40
        api_verdicts.append({"name":r["name"],"status":status,"score":score,"evidence":evidence,"slots":slots,"uses":uses,"helpers":helpers,"xrefs":r["xrefs"]})
    api_verdicts.sort(key=lambda x:x["score"],reverse=True)
    return {"file":str(pe.path.relative_to(root)),"gpa_vas":gpa_vas,"shared_helpers":shared,"apis":api_verdicts}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root",type=Path)
    ap.add_argument("--json",type=Path)
    ap.add_argument("--all-context",action="store_true",help="Print xref/helper/use byte windows for the top candidates")
    ap.add_argument("--objects",action="store_true",help="Verify the pinned WinIsp object resolver with CFG dataflow (uv project dependencies)")
    args=ap.parse_args()
    root=args.root.resolve()
    pes=[]
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() in {".exe",".dll"}:
            pe=parse_pe(p)
            if pe: pes.append(pe)

    print("===== PHASE 6 - DEEP RESOLVER RECONSTRUCTION =====")
    print("Offline/read-only. Reconstructs helper-based GetProcAddress resolution and slot use.")
    print()
    reports=[]
    for pe in pes:
        if args.objects:
            from soc_recon_objects import analyze_objects, print_objects
            object_report = analyze_objects(pe)
            if object_report:
                print_objects(object_report, full=args.all_context)
                reports.append({"file":str(pe.path.relative_to(root)), "apis":[], "object_proof":object_report})
        if not iat_va(pe,"GetProcAddress"):
            continue
        if not any(list(ascii_strings(pe,n)) for n in TARGETS):
            continue
        rep=analyze_pe(pe,root)
        reports.append(rep)
        interesting=[a for a in rep["apis"] if a["status"] != "DATA_ONLY" or a["name"] in {"ReadRegEx","ReadRegsEx","NativeRead"}]
        if not interesting and not rep["shared_helpers"]:
            continue
        print(f"-- {rep['file']} --")
        print(f"GetProcAddress IATs: {', '.join('0x%08X'%x for x in rep['gpa_vas'])}")
        if rep["shared_helpers"]:
            print("Shared resolver-helper candidates:")
            for sh in rep["shared_helpers"][:12]:
                gtag="YES" if sh["gpa_hits"] else "no"
                print(f"  helper file+0x{sh['helper_off']:08X} VA=0x{(sh['helper_va'] or 0):08X} names={','.join(sh['names'])} calls_GetProcAddress={gtag}")
                if sh["gpa_hits"]:
                    print("    GPA calls inside helper: " + ", ".join(f"file+0x{x:08X}" for x in sh["gpa_hits"][:8]))
        for a in interesting[:8]:
            print(f"  {a['name']:<18} {a['status']:<28} score={a['score']} xrefs={len(a['xrefs'])} slots={len(a['slots'])} uses={len(a['uses'])}")
            for ev in a["evidence"][:6]:
                print(f"    evidence: xref file+0x{ev[0]:08X} -> call file+0x{ev[1]:08X} ({ev[2]})")
            for st in a["slots"][:6]:
                print(f"    slot candidate: file+0x{st[0]:08X} {st[1]} -> VA 0x{st[2]:08X}")
            for use in a["uses"][:8]:
                slot,uo,uk,ulen=use
                print(f"    slot use: VA 0x{slot:08X} at file+0x{uo:08X} {uk}")
                setup="; ".join(t for _o,t in arg_summary(pe,uo))
                if setup: print(f"      args: {setup}")
            if args.all_context and a["xrefs"]:
                for xr in a["xrefs"][:3]:
                    print(f"    XREF CONTEXT {a['name']} file+0x{xr['xref_off']:08X} {xr['kind']}")
                    print(hex_context(pe,xr["xref_off"],48,128))
                    for ce in xr["calls"][:5]:
                        if ce["helper_gpa_hits"] or ce["direct_gpa"]:
                            print(f"    RESOLVER CALL CONTEXT file+0x{ce['call_off']:08X}")
                            print(hex_context(pe,ce["call_off"],64,96))
                            if ce["target_off"] is not None and ce["helper_gpa_hits"]:
                                print(f"    HELPER CONTEXT file+0x{ce['target_off']:08X}")
                                print(hex_context(pe,ce["target_off"],32,192))
        print()

    flat=[]
    for rep in reports:
        for a in rep["apis"]:
            flat.append((a["score"],rep["file"],a))
    flat.sort(reverse=True,key=lambda x:x[0])
    print("===== DEEP CAMPAIGN VERDICT =====")
    if flat:
        for score,file,a in flat[:10]:
            print(f"{score:>3}  {file} :: {a['name']} :: {a['status']}")
        score,file,a=flat[0]
        print(f"HEURISTIC_TOP_CANDIDATE={file}::{a['name']}::{a['status']}")
        if a["status"] == "CANDIDATE_RESOLVER_USED":
            print("VERDICT: nearby resolver, slot and use byte patterns need dataflow verification.")
            print("Byte-window candidates still require instruction-boundary, object provenance and ABI verification before runtime use.")
        elif a["status"] in {"CANDIDATE_HELPER_RESOLVER","CANDIDATE_DIRECT_RESOLVER"}:
            print("VERDICT: API-name and GetProcAddress proximity is a candidate, not an ABI proof.")
        elif a["status"] == "STRONG_CODE_XREF":
            print("VERDICT: code xref proven, but resolver linkage still not proven by current patterns.")
    else:
        print("No deep candidates found.")

    if any('object_proof' in report for report in reports):
        print('DEEP_NEXT_TARGET=ASUS_FIRMWARE_SOC_SOURCE_AND_READ_ONLY_ACCESS')
        print('Object resolver and read ABI verified; register address-space and SOC access remain unproven.')
    elif flat:
        print(f"DEEP_NEXT_TARGET={flat[0][1]}::{flat[0][2]['name']}::{flat[0][2]['status']}")

    if args.json:
        args.json.parent.mkdir(parents=True,exist_ok=True)
        args.json.write_text(json.dumps(reports,indent=2,default=str),encoding="utf-8")
        print(f"DEEP_JSON_REPORT={args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

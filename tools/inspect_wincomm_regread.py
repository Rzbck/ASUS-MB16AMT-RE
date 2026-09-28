"""Offline PE/x86 inspection for WinComm general register-read exports.

Goal: identify a read primitive that preserves a real 16/32-bit register address,
for later read-only SOC runtime correlation. No DLL load and no device I/O.
"""
from pathlib import Path
import argparse, struct

TARGETS = ["ReadReg", "ReadRegEx", "ReadRegsEx", "Read32BitRegEx", "Read32BitRegsEx"]


def u16(b, o): return struct.unpack_from('<H', b, o)[0]
def u32(b, o): return struct.unpack_from('<I', b, o)[0]


def pe_info(data: bytes):
    pe = u32(data, 0x3C)
    if data[pe:pe+4] != b'PE\0\0':
        raise SystemExit('not PE')
    machine = u16(data, pe+4)
    nsec = u16(data, pe+6)
    opt = pe+24
    magic = u16(data, opt)
    if magic != 0x10B:
        raise SystemExit('expected PE32')
    exp_rva = u32(data, opt+96)
    sec_off = opt + u16(data, pe+20)
    secs=[]
    for i in range(nsec):
        o=sec_off+i*40
        name=data[o:o+8].split(b'\0',1)[0].decode('ascii','replace')
        vs=u32(data,o+8); va=u32(data,o+12); rawsz=u32(data,o+16); raw=u32(data,o+20)
        secs.append((name,va,max(vs,rawsz),raw))
    def r2o(rva):
        for _,va,sz,raw in secs:
            if va <= rva < va+sz:
                return raw + (rva-va)
        raise KeyError(hex(rva))
    return machine, secs, exp_rva, r2o


def exports(data, exp_rva, r2o):
    e=r2o(exp_rva)
    base=u32(data,e+16); nfunc=u32(data,e+20); nname=u32(data,e+24)
    af=u32(data,e+28); an=u32(data,e+32); ao=u32(data,e+36)
    out=[]
    for i in range(nname):
        nrva=u32(data,r2o(an)+4*i)
        no=r2o(nrva); end=data.index(0,no); name=data[no:end].decode('ascii','replace')
        ordidx=u16(data,r2o(ao)+2*i); frva=u32(data,r2o(af)+4*ordidx)
        out.append((name,base+ordidx,frva))
    return out


def dump(data, off, n=224):
    bs=data[off:off+n]
    for i in range(0,len(bs),16):
        row=bs[i:i+16]
        hx=' '.join(f'{x:02X}' for x in row)
        asc=''.join(chr(x) if 32<=x<127 else '.' for x in row)
        print(f'{i:04X}: {hx:<47}  {asc}')


def clues(bs: bytes):
    print('-- simple ABI/address clues --')
    # EBP stack args [ebp+imm8]
    seen=[]
    for i in range(len(bs)-3):
        if bs[i] in (0x8B,0x89,0xFF,0x83,0x81,0x0F) and i+2 < len(bs):
            # generic ModRM pattern with base EBP disp8: mod=01 r/m=101
            modrm=bs[i+1]
            if (modrm & 0xC7)==0x45:
                disp=bs[i+2]
                seen.append(disp)
        if bs[i:i+2] == b'\x66\x8b' and i+3 < len(bs):
            modrm=bs[i+2]
            if (modrm & 0xC7)==0x45:
                seen.append(bs[i+3])
    if seen:
        print('stack arg offsets seen:', ', '.join(f'[EBP+0x{x:02X}]' for x in sorted(set(seen))))
    else:
        print('stack arg offsets: none found by simple scan')

    # address-destructive masks/ORs worth flagging
    pats=[
        (b'\x0d\x00\xff\x00\x00','OR EAX,0x0000FF00'),
        (b'\x25\xff\x00\x00\x00','AND EAX,0x000000FF'),
        (b'\x25\xff\xff\x00\x00','AND EAX,0x0000FFFF'),
        (b'\x66\x25\xff\x00','AND AX,0x00FF'),
    ]
    for p,label in pats:
        poss=[]; s=0
        while True:
            j=bs.find(p,s)
            if j<0: break
            poss.append(j); s=j+1
        if poss: print(label+':', ', '.join(f'+0x{x:X}' for x in poss))

    # MOVZX from word stack argument: 0F B7 45 xx
    for i in range(len(bs)-4):
        if bs[i:i+3] == b'\x0f\xb7\x45':
            print(f'MOVZX EAX,word [EBP+0x{bs[i+3]:02X}] at +0x{i:X}')
    # direct 32-bit move from stack: 8B 45 xx
    for i in range(len(bs)-3):
        if bs[i:i+2] == b'\x8b\x45':
            print(f'MOV EAX,[EBP+0x{bs[i+2]:02X}] at +0x{i:X}')
    # RET n / RET
    for i,x in enumerate(bs):
        if x==0xC3: print(f'RET at +0x{i:X}')
        if x==0xC2 and i+2<len(bs): print(f'RET {u16(bs,i+1)} at +0x{i:X}')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('root', type=Path)
    args=ap.parse_args()
    p=next(args.root.rglob('WinComm.dll'),None)
    if not p: raise SystemExit('WinComm.dll not found')
    data=p.read_bytes(); machine,secs,exp,r2o=pe_info(data); ex=exports(data,exp,r2o)
    by={n:(o,r) for n,o,r in ex}
    print('ASUS MB16AMT — offline WinComm general register-read inspection')
    print('file:',p); print(f'PE32 machine=0x{machine:04X}'); print('NO DLL LOAD; NO DEVICE I/O')
    print()
    for name in TARGETS:
        if name not in by:
            print(f'===== {name}: NOT EXPORTED =====\n'); continue
        ordn,rva=by[name]; off=r2o(rva)
        print(f'===== {name} ord={ordn} RVA=0x{rva:08X} file=0x{off:08X} =====')
        bs=data[off:off+224]
        dump(data,off,224)
        clues(bs)
        print()
    print('===== INTERPRETATION RULE =====')
    print('Prefer a primitive whose address argument is preserved as 16/32 bits and is not forced into 0xFFxx / low-byte MCU-register space.')
    print('Do not call any candidate at runtime until its parameter count and pointer/output convention are established from this offline inspection.')

if __name__=='__main__': main()

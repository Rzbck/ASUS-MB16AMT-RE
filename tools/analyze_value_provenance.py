"""Reproduce the complete 8:5FEF setting-query contract offline.

Runs bounded instruction interpretation against a separately reconstructed
model. No device access, no input writes, no third-party dependencies.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
from analyze_banked_abi import SHA, inventory, traverse, hits, word, LENGTHS
from emulate_mcs51 import Machine

DIRECT = {0x1C:0xDA3D,0x1D:0xDA3E,0x1E:0xDA3F,0x1F:0xDA41,0x20:0xDA42,
          0x21:0xDA43,0x22:0xDA08,0x24:0xDA17,0x2B:0xD9F9,0x44:0xDA04,0x46:0xDA07}
BITS = {0x28:(0xD9FD,5),0x29:(0xD9FE,6),0x2A:(0xDA00,0),0x2C:(0xD9FF,5),
        0x2D:(0xD9FF,4),0x42:(0xD9FF,4),3:(0xD9FF,4),0x2E:(0xDA00,3),
        4:(0xD9FF,7),0x43:(0xD9FF,7),5:(0xD9FF,6),0x2F:(0xDA0F,0),
        0x30:(0xD9FE,5),0x45:(0xD9FD,2),0x33:(0xD9FD,6),0x35:(0xD9FD,1)}
MAXIMUM = {**{s:100 for s in DIRECT},0x1F:5,0x20:2,0x44:120,0x32:20,0x0C:8,
           **{s:7 for s in range(0x0F,0x17)},**{s:4 for s in range(0x17,0x1C)},
           **{s:100 for s in range(0x50,0x53)},**{s:1 for s in BITS},
           0x23:1,0x25:1,0x5D:1,0x37:0,0x38:0,0x39:0}
STEP = {0x21:10,0x22:20,0x24:25,0x44:10,0x46:20,0x5D:0}


def model(selector, mode, x):
    if selector==0x36:return 1
    if mode==1:return MAXIMUM.get(selector,0)
    if mode==2:return 10 if selector==0x44 else 0
    if mode==3:return STEP.get(selector,1)
    if mode!=0:return 0
    if selector in DIRECT:return x[DIRECT[selector]]
    if selector in BITS:
        a,n=BITS[selector];return 1-((x[a]>>n)&1)
    if 0x0F<=selector<=0x16:return x[0xDA06]&15
    if 0x17<=selector<=0x1B:return x[0xDA0E]>>4
    if 0x50<=selector<=0x52:return max(0,min(100,x[0xDA21+selector-0x50]-28))
    if selector==0x23:
        value=x[0xDA0E]&3
        return 0 if value==1 and not x[0xDA68]&4 else value
    if selector==0x25:return int(x[0xDA44]==0)
    if selector==0x32:return x[0xDA03]&63
    if 0x37<=selector<=0x39:return x[0xDA0B+selector-0x37]&15
    if selector==0x0C:return x[0xDA0A]&15
    if selector==0x5D:return (x[0xDA92]>>4)&1
    return 0


def describe(selector):
    if selector in DIRECT:return f'X[{DIRECT[selector]:04X}]'
    if selector in BITS:
        a,n=BITS[selector];return f'1 - ((X[{a:04X}] >> {n}) & 1)'
    if 0x0F<=selector<=0x16:return 'X[DA06] & 0F'
    if 0x17<=selector<=0x1B:return 'X[DA0E] >> 4'
    if 0x50<=selector<=0x52:return f'clamp(X[{0xDA21+selector-0x50:04X}] - 28, 0, 100)'
    return {0x23:'v=X[DA0E]&3; return 0 if v==1 and DA68.bit2==0 else v',
            0x25:'X[DA44] == 0',0x32:'X[DA03] & 3F',0x36:'1 (every mode)',
            0x37:'X[DA0B] & 0F',0x38:'X[DA0C] & 0F',0x39:'X[DA0D] & 0F',
            0x0C:'X[DA0A] & 0F',0x5D:'(X[DA92] >> 4) & 1'}.get(selector,'0')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('firmware',type=Path);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();data=args.firmware.read_bytes()
    if len(data)!=0xE0000 or hashlib.sha256(data).hexdigest()!=SHA:raise SystemExit('Wrong image')
    t=inventory(data);decoded,*_=traverse(data,t)
    coverage,branches,reads,writes,transfers=set(),set(),set(),set(),set()
    count=0;max_steps=0
    def check(s,m,fill,overrides=None):
        nonlocal count,max_steps
        machine=Machine(data,t,fill)
        for a,v in (overrides or {}).items():machine.x[a]=v
        expected=model(s,m,machine.x)
        machine.sr(7,s);machine.sr(5,m)
        actual=machine.run(8,0x5FEF)
        assert actual==expected,(s,m,fill,actual,expected)
        assert not machine.stack and not machine.calls
        coverage.update(machine.visited);branches.update(machine.branches)
        reads.update(machine.reads);writes.update(machine.writes);transfers.update(machine.transfers)
        count+=1;max_steps=max(max_steps,machine.steps)
    # Exhaust the two byte inputs; then all uniform byte values for mode 0.
    for s in range(256):
        for m in range(256):check(s,m,0)
    for s in range(256):
        for v in range(1,256):check(s,0,v)
    # Independently vary the two fields used by the only coupled-state branch.
    for field in range(4):
        for gate in range(2):check(0x23,0,0,{0xDA0E:field,0xDA68:gate<<2})
    args.out.mkdir(parents=True,exist_ok=True)
    def csvout(name,headers,rows):
        with (args.out/name).open('w',newline='',encoding='utf-8') as f:
            w=csv.writer(f);w.writerow(headers);w.writerows(rows)
    csvout('setting-query-contract.csv',['selector_hex','mode0','mode1','mode2','mode3','mode4_to_FF'],
           [(f'{s:02X}',describe(s),1 if s==0x36 else MAXIMUM.get(s,0),
             1 if s==0x36 else 10 if s==0x44 else 0,1 if s==0x36 else STEP.get(s,1),1 if s==0x36 else 0)
            for s in range(256)])
    csvout('setting-query-xdata.csv',['kind','physical_bank','site','address'],
           [(kind,b,f'{pc:04X}',f'{a:04X}') for kind,items in [('read',reads),('write',writes)] for b,pc,a in sorted(items)])
    csvout('setting-query-transfers.csv',['physical_bank','site','target','is_call','resolved_bank','resolved_address'],
           [(b,f'{pc:04X}',f'{a:04X}',call,t[a][0] if a in t else b,f'{t[a][1] if a in t else a:04X}') for b,pc,a,call in sorted(transfers)])
    callers=[]
    for b in range(14):
        chunk=data[b*65536:(b+1)*65536]
        for target in ([0x1862,0x5FEF] if b==8 else [0x1862]):
            for op in (0x12,2):
                for p in hits(chunk,bytes([op,target>>8,target&255])):
                    callers.append((b,f'{p:04X}','LCALL' if op==0x12 else 'LJMP',f'{target:04X}',(b,p) in decoded))
    csvout('setting-query-callers.csv',['physical_bank','site','kind','target','cfg_boundary'],sorted(callers))
    pc=0x5FEF;static_starts=set();conditional=set()
    while pc<0x65A0:
        static_starts.add((8,pc));op=data[8*65536+pc]
        if op in (0x10,0x20,0x30,0x40,0x50,0x60,0x70,0xD5) or 0xB4<=op<=0xBF or 0xD8<=op<=0xDF:conditional.add(pc)
        pc+=LENGTHS[op]
    summary={'sha256':SHA,'entry':'8:5FEF','end_exclusive':'8:65A0','thunk':'1862',
             'tests':count,'max_steps':max_steps,'main_instruction_starts':len(static_starts),
             'unvisited_main_starts':[f'{p:04X}' for b,p in sorted(static_starts-coverage)],
             'one_sided_conditions':{f'{p:04X}':[v for b,q,v in sorted(branches) if b==8 and q==p] for p in sorted(conditional) if len({v for b,q,v in branches if b==8 and q==p})<2},
             'read_addresses':[f'{a:04X}' for a in sorted({a for _,_,a in reads})],
             'write_addresses':[f'{a:04X}' for a in sorted({a for _,_,a in writes})],
             'banks_executed':sorted({b for b,p in coverage}),
             'limits':'Finite offline tests plus complete manual branch reconstruction; not all combinations of entire XDATA or hardware timing. Logical-to-physical identity is the working static model. Arithmetic flags AC/OV/parity are not emulated and must not be consumed on tested paths.'}
    (args.out/'setting-query-summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()

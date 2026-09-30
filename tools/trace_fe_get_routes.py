"""Bounded offline FE GET dispatch inventory; stops at service entrypoints."""
import argparse
import hashlib
import json
from pathlib import Path
from analyze_banked_abi import SHA, inventory
from emulate_mcs51 import Machine
class Boundary(Exception):pass
class Route(Machine):
    def jump(self,t,call=False):
        if self.bank==12 and t in (0xF7F9,0xF936,0xF684,0xFDA4,0x1508):
            self.destination=t
            raise Boundary()
        super().jump(t,call)
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('firmware',type=Path);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    data=args.firmware.read_bytes();assert hashlib.sha256(data).hexdigest()==SHA
    thunks=inventory(data);routes={};count=0
    # All primary/secondary selectors, plus metadata gate values explicitly used
    # by the decoder. This audits dispatch, not transitive service semantics.
    cases=[(a,b,0,0) for a in range(256) for b in range(256)]
    cases.extend((0xE1,b,c,d) for b in (0xA4,0xA7) for c in (1,7) for d in (0,1))
    for primary,secondary,third,fourth in cases:
        m=Route(data,thunks);m.x[0xD990:0xD999]=bytes([0x51,0x87,1,0xFE,primary,secondary,third,fourth,4]);m.destination=None
        try:m.run(12,0xE431,budget=500)
        except Boundary:pass
        assert not {a for _,_,a in m.reads}&{0xDA4C,0xD9F7,0xDCC2}
        assert {a for _,_,a in m.writes}<={0xD820,*range(0xD83E,0xD843)}
        if m.destination is not None:
            key=f'{primary:02X}'
            entry=routes.setdefault(key,{})
            label=f'{m.destination:04X}'
            if m.destination==0x1508:label+=' slave='+f'{m.r(7):02X}'
            entry.setdefault(label,set()).add(f'{secondary:02X}')
        count+=1
    report=dict(sha256=SHA,checks=count,routes={a:{b:sorted(c) for b,c in entries.items()} for a,entries in routes.items()},
        boundaries={'F7F9':'fixed metadata/code strings','F936':'diagnostic flash-log path; not exercised live','F684':'storage-related read dispatcher; not exercised live','FDA4':'formatted setting reply','1508':'internal software I2C read'},
        limits=['Exhaustive two selector bytes only; conditional metadata bytes tested at listed boundary cases','Execution stops before services; no claim of exhaustive service side-effect or indirect-memory analysis','No direct DA4C/cache access in the audited dispatch; services require separate audit','No hardware requests made'])
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print('Verified',count,'dispatch cases; primary selectors:',','.join(routes))
if __name__=='__main__':main()

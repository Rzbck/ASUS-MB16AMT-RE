"""Verify nominal battery timer setup and countdown offline, no hardware access."""
import argparse
import hashlib
import json
from pathlib import Path
from analyze_banked_abi import SHA, inventory
from emulate_mcs51 import Machine

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('firmware',type=Path)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();data=args.firmware.read_bytes()
    assert hashlib.sha256(data).hexdigest()==SHA
    thunks=inventory(data)
    assert thunks[0x16E2]==(5,0xE268)
    assert data[0x4F3B3:0x4F3BA]==bytes.fromhex('7f 01 7e 00 12 16 e2')
    assert data[0x9BF6F:0x9BF7C]==bytes.fromhex('90 da 52 74 03 f0 a3 74 e8 f0 12 e7 7f')
    rows=[]
    for control,clock,counts in ((2,0,7308),(0,8,2333),(0,0,1193)):
        m=Machine(data,thunks);m.sr(7,1);m.x[0xFFED]=control;m.x[9]=clock
        m.run(5,0xE268,budget=2000)
        assert m.x[0xD988:0xD98A]==bytes.fromhex('00 01')
        assert m.x[0xD98C:0xD98E]==bytes.fromhex('03 e8')
        reload=m.x[0xD95E]*256+m.x[0xD960]
        assert reload==65535-counts
        assert m.ram[0x8B]==m.x[0xD960] and m.ram[0x8D]==m.x[0xD95E]
        rows.append(dict(ffed=control,clock_selector=clock,divider=1,intermediate_us=1000,reload=f'{reload:04X}',subtracted_counts=counts))
    for count in range(1002):
        m=Machine(data,thunks);m.x[0xDA52:0xDA54]=count.to_bytes(2,'big')
        m.run(4,0xF90A,budget=200)
        assert int.from_bytes(m.x[0xDA52:0xDA54],'big')==max(0,count-1)
    report=dict(sha256=SHA,setup='4:F3B3 -> 16E2 -> 5:E268 (argument 1)',
        clock_cases=rows,countdown_checks=1002,updater='9:BF65 checks zero, reloads 1000, calls 9:E77F',
        confidence='Nominal 1 ms timer matches ScalerTimer1SetTimerCount in the public reference; normal battery period approximately 1 s, filter step approximately 13 s while differing.',
        limitations=['Physical clock frequency and ISR jitter not measured','DA58 can defer acquisition; DA4C=0 has an additional updater path','This does not directly read or synchronize the live display cache'])
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,indent=2))
if __name__=='__main__':main()

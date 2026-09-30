"""Offline verification of FE/EF/F0 internal gauge READ proxy; no hardware I/O."""
import argparse
import hashlib
import json
from pathlib import Path
from analyze_banked_abi import SHA, inventory
from emulate_mcs51 import Machine

class Done(Exception): pass
class Proxy(Machine):
    def __init__(self,data,thunks,payload,success=True):
        super().__init__(data,thunks)
        self.payload,self.success,self.requests=payload,success,0
    def jump(self,t,call=False):
        if t==0x1508:
            assert self.bank==12 and call
            assert tuple(self.r(i) for i in (7,5,2,3))==(0xAA,1,0,0x10)
            assert self.x[0xD83E:0xD843]==bytes.fromhex('00 04 01 d9 c2')
            self.requests+=1
            if self.success:self.x[0xD9C2:0xD9C6]=self.payload
            self.c=self.success
            return
        if t==0x1298:
            assert self.bank==12 and call
            raise Done()
        super().jump(t,call)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('firmware',type=Path)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    data=args.firmware.read_bytes()
    assert hashlib.sha256(data).hexdigest()==SHA
    thunks=inventory(data)
    assert thunks[0x1508]==(0,0x6D00)
    records=[]
    for payload in (bytes.fromhex('34 12 78 56'), bytes.fromhex('e8 03 e8 03')):
        for success in (True,False):
            m=Proxy(data,thunks,payload,success)
            m.x[0xD990:0xD999]=bytes.fromhex('51 87 01 fe ef f0 00 10 04')
            m.x[0xD9C2:0xD9C6]=bytes.fromhex('02 00 10 00')
            try:m.run(12,0xE431,budget=3000)
            except Done:pass
            else:raise AssertionError('No response')
            assert m.requests==1
            frame=bytes(m.x[0xD9C0:0xD9C7])
            assert frame[:2]==bytes.fromhex('6e 84')
            assert frame[2:6]==(payload if success else bytes.fromhex('02 00 10 00'))
            check=0x50
            for byte in frame:check^=byte
            assert check==0
            assert {a for _,_,a in m.writes}<={0xD820,*range(0xD83E,0xD843),*range(0xD9C0,0xD9C7)}
            records.append(dict(i2c_success=success,frame=frame.hex()))
    report=dict(sha256=SHA,entry='12:E431',command='GET 01 / VCP FE / subcommand EF / target F0',
        payload='01 fe ef f0 00 10 04',internal_read='0:6D00 AA:10 length=4',
        tests=records,warning='I2C failure is not reported; stale TX bytes may have a valid checksum. Reject prior brightness payload 02 00 10 00. No live percentage claim from framing alone.')
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()

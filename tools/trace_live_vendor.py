"""Observe native vendor calls in an already-running approved read harness.
Local JSONL may contain vendor buffers: review/sanitize before publication.
Run with uv run --with frida python tools/trace_live_vendor.py --pid ... --out ...
"""
import argparse,json,time
from pathlib import Path

JS=r'''
const watched=['I2CRead','I2CWrite','I2CReadEx','DDCCIRead','DDCCIWrite','ReadRegEx','ReadRegsEx','NativeRead','NativeWrite'];
const attached=new Set();
function bytes(p,n){try{return Array.from(new Uint8Array(p.readByteArray(Math.min(n,64)))).map(x=>x.toString(16).padStart(2,'0')).join('');}catch(e){return null;}}
function instrument(m){
 if(/winusb|rhub|rthub|comm_|wincomm|hid\.dll/i.test(m.name))send({kind:'module',name:m.name});
 if(m.name.toLowerCase()==='wincomm.dll'){
  for(const name of watched){let a=m.findExportByName(name);if(!a||attached.has(a.toString()))continue;attached.add(a.toString());
   // Verified signatures: I2CRead/Write and DDCCIRead/Write (slave,sub,length,buffer).
   if(!['I2CRead','I2CWrite','I2CReadEx','DDCCIRead','DDCCIWrite'].includes(name)){send({kind:'export_present',dll:m.name,function:name});continue;}
   Interceptor.attach(a,{onEnter(args){this.rec={kind:'call',timestamp:new Date().toISOString(),dll:m.name,function:name,slave:args[0].toUInt32()&255,sub:args[1].toUInt32()&255,size:args[2].toUInt32()&65535};this.buf=args[3];this.rec.before=bytes(this.buf,this.rec.size);},onLeave(rc){this.rec.rc=rc.toInt32();this.rec.after=bytes(this.buf,this.rec.size);send(this.rec);}});
  }
 }
 if(m.name.toLowerCase()==='winusb.dll' && Process.pointerSize===4){
  let a=m.findExportByName('WinUsb_ControlTransfer');
  if(a&&!attached.has(a.toString())){attached.add(a.toString());Interceptor.attach(a,{onEnter(args){let lo=args[1].toUInt32(),hi=args[2].toUInt32();this.rec={kind:'usb_control',timestamp:new Date().toISOString(),request_type:lo&255,request:(lo>>>8)&255,value:lo>>>16,index:hi&65535,length:hi>>>16,buffer_length:args[4].toUInt32()};this.buf=args[3];this.rec.before=bytes(this.buf,this.rec.buffer_length);},onLeave(rc){this.rec.ok=rc.toInt32()!=0;this.rec.after=bytes(this.buf,this.rec.buffer_length);send(this.rec);}});}
 }
 if(m.name.toLowerCase()==='kernelbase.dll'){
  let a=m.findExportByName('DeviceIoControl');if(a&&!attached.has(a.toString())){attached.add(a.toString());Interceptor.attach(a,{onEnter(args){this.rec={kind:'ioctl',timestamp:new Date().toISOString(),code:args[1].toUInt32(),input_size:args[3].toUInt32(),output_size:args[5].toUInt32(),input:bytes(args[2],args[3].toUInt32())};this.out=args[4];},onLeave(rc){this.rec.ok=rc.toInt32()!=0;this.rec.output=bytes(this.out,this.rec.output_size);send(this.rec);}});}
 }
}
Process.attachModuleObserver({onAdded:instrument});
send({kind:'ready',pid:Process.id});
'''
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--pid',type=int,required=True);ap.add_argument('--seconds',type=int,default=45);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 if not 1<=a.seconds<=300:raise SystemExit('Duration must be 1..300 seconds')
 a.out.parent.mkdir(parents=True,exist_ok=True)
 import frida
 session=frida.attach(a.pid)
 try:
  with a.out.open('w',encoding='utf-8') as f:
   def message(m,data):
    f.write(json.dumps(m)+'\n');f.flush()
   script=session.create_script(JS);script.on('message',message);script.load();time.sleep(a.seconds);script.unload()
 finally:session.detach()
 print('Detached; local trace:',a.out)
if __name__=='__main__':main()

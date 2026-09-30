// Read-only Windows USB hub inventory. No device paths or serial strings emitted.
// Packed USB layouts and IOCTL values checked against Windows SDK usbioctl.h.
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class UsbPowerInspect {
 [StructLayout(LayoutKind.Sequential)] struct InterfaceData {public int Size; public Guid Class; public int Flags; public IntPtr Reserved;}
 [DllImport("setupapi.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern IntPtr SetupDiGetClassDevs(ref Guid g,string e,IntPtr w,uint f);
 [DllImport("setupapi.dll",SetLastError=true)] static extern bool SetupDiEnumDeviceInterfaces(IntPtr s,IntPtr d,ref Guid g,uint i,ref InterfaceData data);
 [DllImport("setupapi.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern bool SetupDiGetDeviceInterfaceDetail(IntPtr s,ref InterfaceData d,IntPtr detail,uint size,out uint needed,IntPtr dev);
 [DllImport("setupapi.dll")] static extern bool SetupDiDestroyDeviceInfoList(IntPtr s);
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern SafeFileHandle CreateFile(string p,uint a,uint share,IntPtr sec,uint disp,uint flags,IntPtr template);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool DeviceIoControl(SafeFileHandle h,uint ctl,byte[] input,uint ni,byte[] output,uint no,out uint returned,IntPtr o);
 static ushort U16(byte[] b,int p){return BitConverter.ToUInt16(b,p);}
 static uint U32(byte[] b,int p){return BitConverter.ToUInt32(b,p);}
 static void Put(byte[] b,int p,uint v){Array.Copy(BitConverter.GetBytes(v),0,b,p,4);}
 static bool Query(SafeFileHandle h,int function,byte[] b){uint returned;return DeviceIoControl(h,0x220000u+((uint)function<<2),b,(uint)b.Length,b,(uint)b.Length,out returned,IntPtr.Zero);}
 static List<string> Hubs(){
  Guid g=new Guid("f18a0e88-c30c-11d0-8815-00a0c906bed8");IntPtr set=SetupDiGetClassDevs(ref g,null,IntPtr.Zero,18);
  if(set==new IntPtr(-1))throw new Exception("Hub enumeration failed");var paths=new List<string>();
  try {for(uint i=0;i<128;i++){InterfaceData d=new InterfaceData();d.Size=Marshal.SizeOf(d);if(!SetupDiEnumDeviceInterfaces(set,IntPtr.Zero,ref g,i,ref d))break;uint needed;SetupDiGetDeviceInterfaceDetail(set,ref d,IntPtr.Zero,0,out needed,IntPtr.Zero);if(needed<6||needed>65536)throw new Exception("Interface size invalid");IntPtr p=Marshal.AllocHGlobal((int)needed);try{Marshal.WriteInt32(p,IntPtr.Size==8?8:6);if(!SetupDiGetDeviceInterfaceDetail(set,ref d,p,needed,out needed,IntPtr.Zero))throw new Exception("Hub path query failed");paths.Add(Marshal.PtrToStringUni(IntPtr.Add(p,4)));}finally{Marshal.FreeHGlobal(p);}}}finally{SetupDiDestroyDeviceInfoList(set);}return paths;
 }
 static void Bos(SafeFileHandle h,int hub,int port) {
  byte[] header=new byte[17];Put(header,0,(uint)port);header[4]=0x80;header[5]=6;header[7]=15;header[10]=5;
  if(!Query(h,260,header)||header[12]!=5||header[13]!=15){Console.WriteLine("BOS H{0}:{1} unavailable error={2}",hub,port,Marshal.GetLastWin32Error());return;}
  int total=U16(header,14);if(total<5||total>4096)throw new Exception("Invalid BOS size");
  byte[] bos=new byte[12+total];Put(bos,0,(uint)port);bos[4]=0x80;bos[5]=6;bos[7]=15;bos[10]=(byte)total;bos[11]=(byte)(total>>8);
  if(!Query(h,260,bos))return;
  for(int offset=17;offset<bos.Length;){int len=bos[offset];if(len<3||offset+len>bos.Length)throw new Exception("Malformed BOS");int type=bos[offset+2];
   // Omit container IDs and platform UUID payloads (potential device identifiers).
   Console.WriteLine("BOS H{0}:{1} capability={2:X2} length={3}{4}",hub,port,type,len,(type==6||type==8||type==9||type==13)?" fields="+BitConverter.ToString(bos,offset,len):"");offset+=len;}
 }
 public static int Main(){
  var paths=Hubs();Console.WriteLine("USB_POWER_INSPECT utc={0:o} hubs={1}; descriptor current is NOT measured input current",DateTime.UtcNow,paths.Count);
  for(int n=0;n<paths.Count;n++)using(var h=CreateFile(paths[n],0xC0000000,3,IntPtr.Zero,3,0,IntPtr.Zero)){
   if(h.IsInvalid){Console.WriteLine("HUB H{0} open_error={1}",n,Marshal.GetLastWin32Error());continue;}
   byte[] hub=new byte[256];if(!Query(h,277,hub)){Console.WriteLine("HUB H{0} info_error={1}",n,Marshal.GetLastWin32Error());continue;}
   int ports=U16(hub,4);Console.WriteLine("HUB H{0} type={1} ports={2}",n,U32(hub,0),ports);
   if(ports>64)throw new Exception("Invalid port count");
   for(int port=1;port<=ports;port++){
    byte[] c=new byte[4096];Put(c,0,(uint)port);if(!Query(h,274,c)){Console.WriteLine("PORT H{0}:{1} error={2}",n,port,Marshal.GetLastWin32Error());continue;}
    uint status=U32(c,31);if(status==0)continue;
    if(status!=1){Console.WriteLine("PORT H{0}:{1} status={2}",n,port,status);continue;}
    if(c[4]!=18||c[5]!=1)throw new Exception("Invalid device descriptor");
    byte[] v2=new byte[16];Put(v2,0,(uint)port);Put(v2,4,16);Put(v2,8,7);bool v2ok=Query(h,279,v2);
    byte[] props=new byte[4096];Put(props,0,(uint)port);bool propok=Query(h,278,props);
    if(U16(c,12)==0x0BDA || U16(c,12)==0x17E9) Bos(h,n,port);
    bool ss=v2ok&&(U32(v2,12)&1)!=0;
    string child="";
    if(c[24]!=0){byte[] childName=new byte[4096];Put(childName,0,(uint)port);if(Query(h,261,childName)){string path="\\\\.\\"+System.Text.Encoding.Unicode.GetString(childName,8,childName.Length-8).TrimEnd('\0');for(int j=0;j<paths.Count;j++)if(string.Equals(paths[j].Substring(4),path.Substring(4),StringComparison.OrdinalIgnoreCase))child="H"+j;}}
    byte[] cfg=new byte[21];Put(cfg,0,(uint)port);cfg[4]=0x80;cfg[5]=6;cfg[7]=2;cfg[10]=9;bool cfgok=Query(h,260,cfg)&&cfg[12]==9&&cfg[13]==2;
    Console.WriteLine("PORT H{0}:{1} vid={2:X4} pid={3:X4} bcdUSB={4:X4} speed={5} ss={6} child={7} protocols={8} typeC={9} config={10} bMaxPower_mA={11} self_powered_capable={12} config_ok={13}",n,port,U16(c,12),U16(c,14),U16(c,6),c[23],ss,child,v2ok?U32(v2,8).ToString():"unknown",propok?((U32(props,8)&8)!=0).ToString():"unknown",c[22],cfgok?(cfg[20]*(ss?8:2)).ToString():"unknown",cfgok?((cfg[19]&64)!=0).ToString():"unknown",cfgok);
   }
  }return 0;
 }
}

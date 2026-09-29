// Narrow live transport validation. No SET VCP, debug switch, ISP or arbitrary
// register access. DDCCIWrite is used ONLY to send the fixed GET VCP request.
// Build x86; WinComm's exports are cdecl (verified in the bundled PE32 image).
using System;
using System.IO;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Threading;
using System.Security.Principal;

static class SocReadBench {
    const string ExpectedWinComm = "d237f4fbe3ab3acfc4170558785b422aeaea055627522510105f5517b0d78739";
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode)] static extern bool SetDllDirectory(string path);
    [DllImport("WinComm.dll", CallingConvention=CallingConvention.Cdecl)] static extern void Initiallize();
    [DllImport("WinComm.dll",CharSet=CharSet.Unicode,CallingConvention=CallingConvention.Cdecl)] static extern void SetCurWorkingPath(string path);
    [DllImport("WinComm.dll",CharSet=CharSet.Unicode,CallingConvention=CallingConvention.Cdecl)] static extern void SetSettingFilePath(string path);
    [DllImport("WinComm.dll", CallingConvention=CallingConvention.Cdecl)] static extern int GetCommCount();
    [DllImport("WinComm.dll", CallingConvention=CallingConvention.Cdecl)] static extern int SetCommByID(int id);
    [DllImport("WinComm.dll", CallingConvention=CallingConvention.Cdecl)] static extern int GetCommID();
    [DllImport("WinComm.dll", CallingConvention=CallingConvention.Cdecl,SetLastError=true)] static extern int InitialDev();
    [DllImport("WinComm.dll", CallingConvention=CallingConvention.Cdecl)] static extern int ReleaseDev();
    [DllImport("WinComm.dll", CallingConvention=CallingConvention.Cdecl)] static extern byte GetDeviceCount();
    [DllImport("WinComm.dll", CallingConvention=CallingConvention.Cdecl)] static extern int GetDebugMode();
    [DllImport("WinComm.dll", CallingConvention=CallingConvention.Cdecl)] static extern byte GetDebugSlave();
    [DllImport("WinComm.dll", CallingConvention=CallingConvention.Cdecl)] static extern byte GetIspSlave();
    [DllImport("WinComm.dll", CallingConvention=CallingConvention.Cdecl)] static extern byte GetIspContinuousSlave();
    [DllImport("WinComm.dll", CallingConvention=CallingConvention.Cdecl)] static extern int I2CRead(byte slave, byte sub, ushort length, IntPtr output);
    [DllImport("WinComm.dll", CallingConvention=CallingConvention.Cdecl)] static extern int I2CReadEx(byte slave, byte sub, ushort length, IntPtr output, int increment);
    [DllImport("WinComm.dll", CallingConvention=CallingConvention.Cdecl)] static extern int DDCCIRead(byte slave, byte sub, ushort length, IntPtr output);
    [DllImport("WinComm.dll", CallingConvention=CallingConvention.Cdecl)] static extern int DDCCIWrite(byte slave, byte sub, ushort length, byte[] input);

    delegate int Reader(IntPtr output);
    [StructLayout(LayoutKind.Sequential,CharSet=CharSet.Unicode)] struct Physical {
        public IntPtr Handle;
        [MarshalAs(UnmanagedType.ByValTStr,SizeConst=128)] public string Description;
    }
    delegate bool MonitorCallback(IntPtr monitor,IntPtr dc,IntPtr rect,IntPtr data);
    [StructLayout(LayoutKind.Sequential,CharSet=CharSet.Unicode)] struct MonitorInfo {
        public int Size, Left, Top, Right, Bottom, WorkLeft, WorkTop, WorkRight, WorkBottom, Flags;
        [MarshalAs(UnmanagedType.ByValTStr,SizeConst=32)] public string Device;
    }
    [StructLayout(LayoutKind.Sequential,CharSet=CharSet.Unicode)] struct DisplayDevice {
        public int Size;
        [MarshalAs(UnmanagedType.ByValTStr,SizeConst=32)] public string Name;
        [MarshalAs(UnmanagedType.ByValTStr,SizeConst=128)] public string Description;
        public int Flags;
        [MarshalAs(UnmanagedType.ByValTStr,SizeConst=128)] public string Id;
        [MarshalAs(UnmanagedType.ByValTStr,SizeConst=128)] public string Key;
    }
    [DllImport("user32.dll",CharSet=CharSet.Unicode)] static extern bool GetMonitorInfo(IntPtr monitor,ref MonitorInfo info);
    [DllImport("user32.dll",CharSet=CharSet.Unicode)] static extern bool EnumDisplayDevices(string device,uint number,ref DisplayDevice info,uint flags);
    [DllImport("user32.dll")] static extern bool EnumDisplayMonitors(IntPtr dc,IntPtr clip,MonitorCallback callback,IntPtr data);
    [DllImport("dxva2.dll",SetLastError=true)] static extern bool GetNumberOfPhysicalMonitorsFromHMONITOR(IntPtr monitor,out uint count);
    [DllImport("dxva2.dll",SetLastError=true)] static extern bool GetPhysicalMonitorsFromHMONITOR(IntPtr monitor,uint count,[Out] Physical[] physical);
    [DllImport("dxva2.dll",SetLastError=true)] static extern bool DestroyPhysicalMonitors(uint count,Physical[] physical);
    [DllImport("dxva2.dll",SetLastError=true)] static extern bool GetVCPFeatureAndVCPFeatureReply(IntPtr monitor,byte code,out uint type,out uint current,out uint maximum);
    static void WindowsDdc() {
        int matched=0;
        MonitorCallback cb=delegate(IntPtr monitor,IntPtr dc,IntPtr rect,IntPtr data) {
            MonitorInfo mi=new MonitorInfo(); mi.Size=Marshal.SizeOf(mi); GetMonitorInfo(monitor,ref mi);
            bool target=false;
            for(uint index=0;index<16;index++) {
                DisplayDevice device=new DisplayDevice(); device.Size=Marshal.SizeOf(device);
                if(!EnumDisplayDevices(mi.Device,index,ref device,0)) break;
                if(device.Id!=null && device.Id.IndexOf("AUS1661",StringComparison.OrdinalIgnoreCase)>=0) target=true;
            }
            uint count;
            if(!GetNumberOfPhysicalMonitorsFromHMONITOR(monitor,out count)||count==0||count>16) {Console.WriteLine("WINDOWS_DDC {0} target={1} physical_count_unavailable error={2}",mi.Device,target,Marshal.GetLastWin32Error());return true;}
            Physical[] physical=new Physical[count];
            if(!GetPhysicalMonitorsFromHMONITOR(monitor,count,physical)) return true;
            try {
                foreach(Physical p in physical) {
                    Console.WriteLine("WINDOWS_DISPLAY {0} description={1} matched_AUS1661={2}",mi.Device,p.Description,target);
                    if(!target && (p.Description==null||p.Description.IndexOf("MB16AMT",StringComparison.OrdinalIgnoreCase)<0)) continue;
                    matched++; Console.WriteLine("WINDOWS_DDC target={0}",p.Description);
                    for(int n=0;n<3;n++) {
                        uint type,current,maximum;
                        bool ok=GetVCPFeatureAndVCPFeatureReply(p.Handle,0x10,out type,out current,out maximum);
                        int error=ok?0:Marshal.GetLastWin32Error();
                        Console.WriteLine("WINDOWS_DDC VCP10 sample={0} ok={1} win32={2} current={3} max={4}",n,ok,error,current,maximum);
                        Thread.Sleep(100);
                    }
                }
            } finally {DestroyPhysicalMonitors(count,physical);}
            return true;
        };
        EnumDisplayMonitors(IntPtr.Zero,IntPtr.Zero,cb,IntPtr.Zero);
        Console.WriteLine("WINDOWS_DDC matching_physical_monitors={0}",matched);
    }
    sealed class Sample {
        public int Rc; public byte[] Bytes; public bool Changed, Guards;
        public long Milliseconds;
    }
    static Sample Read(int length, byte fill, Reader reader) {
        IntPtr memory=Marshal.AllocHGlobal(length+32);
        try {
            for(int i=0;i<length+32;i++) Marshal.WriteByte(memory,i,0xD3);
            for(int i=0;i<length;i++) Marshal.WriteByte(memory,16+i,fill);
            Stopwatch sw=Stopwatch.StartNew(); int rc=reader(IntPtr.Add(memory,16)); sw.Stop();
            Sample s=new Sample {Rc=rc,Bytes=new byte[length],Guards=true,Milliseconds=sw.ElapsedMilliseconds};
            Marshal.Copy(IntPtr.Add(memory,16),s.Bytes,0,length);
            for(int i=0;i<length;i++) if(s.Bytes[i]!=fill) s.Changed=true;
            for(int i=0;i<16;i++) if(Marshal.ReadByte(memory,i)!=0xD3 || Marshal.ReadByte(memory,16+length+i)!=0xD3) s.Guards=false;
            if(!s.Guards) throw new InvalidOperationException("Output guard overwritten; aborting.");
            return s;
        } finally { Marshal.FreeHGlobal(memory); }
    }
    static string Hash(string path) {
        using(var h=SHA256.Create()) using(var f=File.OpenRead(path))
            return BitConverter.ToString(h.ComputeHash(f)).Replace("-", "").ToLowerInvariant();
    }
    static bool Edid(byte[] b) {
        if(b.Length!=128) return false;
        byte[] header={0,255,255,255,255,255,255,0};
        for(int i=0;i<8;i++) if(b[i]!=header[i]) return false;
        int sum=0; foreach(byte x in b) sum+=x;
        return (sum&255)==0;
    }
    static bool Vcp(byte[] b, byte code) {
        if(b.Length<11 || b[0]!=0x6E || b[1]!=0x88 || b[2]!=2 || b[3]!=0 || b[4]!=code) return false;
        int checksum=0x50; for(int i=0;i<11;i++) checksum^=b[i];
        return checksum==0;
    }
    static string Identity(byte[] b) {
        if(!Edid(b)) return "invalid";
        int m=(b[8]<<8)|b[9];
        string maker=""+(char)(64+((m>>10)&31))+(char)(64+((m>>5)&31))+(char)(64+(m&31));
        return maker+" product="+((b[11]<<8)|b[10]).ToString("X4");
    }
    static void Show(string name,int n,Sample s,bool valid,string detail) {
        Console.WriteLine("{0} sample={1} rc=0x{2:X8} changed={3} guards={4} valid={5} ms={6} {7}",
            name,n,s.Rc,s.Changed,s.Guards,valid,s.Milliseconds,detail);
    }
    static void EdidTest(string name,Reader reader) {
        byte[] previous=null; int good=0; bool stable=true;
        for(int n=0;n<3;n++) {
            Sample s=Read(128,(byte)(n==0?0xA5:n==1?0x5A:0xC3),reader);
            bool valid=s.Rc==0 && s.Changed && Edid(s.Bytes);
            Show(name,n,s,valid,Identity(s.Bytes));
            if(!valid) break;
            if(previous!=null && BitConverter.ToString(previous)!=BitConverter.ToString(s.Bytes)) stable=false;
            previous=s.Bytes; good++; Thread.Sleep(100);
        }
        Console.WriteLine("{0} VERDICT={1} samples={2} stable={3}",name,good==3&&stable?"CONFIRMED_EDID_READ":"REJECTED_FOR_SNAPSHOTS",good,stable);
    }
    static void DdcTest(string name,Reader reader) {
        int good=0; int? prior=null; bool stable=true;
        for(int n=0;n<3;n++) {
            // Only the read-request opcode 01, only known brightness VCP 10.
            int request=DDCCIWrite(0x6E,0x51,2,new byte[]{1,0x10});
            Console.WriteLine("GET_VCP_10 request rc=0x{0:X8}",request);
            if(request!=0) break;
            Thread.Sleep(100);
            // Extra capacity protects against the vendor DDCCIRead copy using
            // the returned frame length; only the requested 11 bytes are parsed.
            Sample s=Read(256,(byte)(n==0?0xA5:n==1?0x5A:0xC3),reader);
            bool valid=s.Rc==0 && s.Changed && Vcp(s.Bytes,0x10);
            int value=(s.Bytes[8]<<8)|s.Bytes[9];
            Show(name,n,s,valid,valid?"brightness="+value+" max="+((s.Bytes[6]<<8)|s.Bytes[7]):"frame="+BitConverter.ToString(s.Bytes,0,11));
            if(!valid) break;
            if(prior.HasValue && prior.Value!=value) stable=false;
            prior=value; good++; Thread.Sleep(100);
        }
        Console.WriteLine("{0} VERDICT={1} samples={2} stable={3}",name,good==3?"CONFIRMED_DDC_GET":"REJECTED_FOR_SNAPSHOTS",good,stable);
    }
    static void PointerMap() {
        ProcessModule win=null;
        foreach(ProcessModule m in Process.GetCurrentProcess().Modules) if(m.ModuleName.Equals("WinComm.dll",StringComparison.OrdinalIgnoreCase)) win=m;
        if(win==null) return;
        string[] names={"I2CRead","I2CWrite","NativeRead","backend_GetCommID","InitialDev","GetDeviceCount"};
        int[] rvas={0x1B2970,0x1B2974,0x1B2940,0x1B2984,0x1B298C,0x1B2928};
        for(int i=0;i<rvas.Length;i++) {
            uint p=unchecked((uint)Marshal.ReadInt32(IntPtr.Add(win.BaseAddress,rvas[i])));
            string target="NULL";
            foreach(ProcessModule m in Process.GetCurrentProcess().Modules) {
                uint a=unchecked((uint)m.BaseAddress.ToInt32());
                if(p>=a && (ulong)p<(ulong)a+(uint)m.ModuleMemorySize) target=m.ModuleName+"+0x"+(p-a).ToString("X");
            }
            Console.WriteLine("LIVE_RESOLVER {0} -> {1}",names[i],target);
        }
    }
    static void SelfTest() {
        byte[] e=new byte[128]; for(int i=1;i<7;i++) e[i]=255; e[127]=6;
        if(!Edid(e)) throw new Exception("EDID positive fixture"); e[8]=1;
        if(Edid(e)) throw new Exception("EDID checksum rejection");
        byte[] v={0x6E,0x88,2,0,0x10,0,0,100,0,40,0};
        v[10]=0x50; for(int i=0;i<10;i++) v[10]^=v[i];
        if(!Vcp(v,0x10)||Vcp(v,0xCA)) throw new Exception("VCP response validation");
        v[10]^=1; if(Vcp(v,0x10)) throw new Exception("VCP checksum rejection");
        Sample s=Read(8,0xA5,delegate(IntPtr p){return 0;});
        if(s.Changed||!s.Guards) throw new Exception("Unchanged buffer detection");
        Console.WriteLine("SELF_TEST_PASS: checksums, request identity, sentinels, guards. No DLL loaded.");
    }
    static int Main(string[] args) {
        try {
            if(args.Length==1 && args[0]=="--self-test") {SelfTest();return 0;}
            if(args.Length==0 || args[0]=="--help") {
                Console.WriteLine("SocReadBench --run | --ddc-only | --self-test. Fixed EDID/GET VCP transport validation; no memory sweep."); return 0;
            }
            if(args.Length!=1||(args[0]!="--run" && args[0]!="--ddc-only")) throw new ArgumentException("Use --run, --ddc-only or --self-test.");
            if(IntPtr.Size!=4) throw new Exception("x86 host required");
            if(!new WindowsPrincipal(WindowsIdentity.GetCurrent()).IsInRole(WindowsBuiltInRole.Administrator)) throw new Exception("Run elevated: the vendor bridge loader requires administrator rights.");
            string root=AppDomain.CurrentDomain.BaseDirectory;
            if(Hash(Path.Combine(root,"WinComm.dll"))!=ExpectedWinComm) throw new Exception("Unrecognized WinComm.dll fingerprint");
            if(Hash(Path.Combine(root,"Comm","Comm_UsbHubI2C.dll"))!="90f61a228eb4c58dfca72e597e5366549483022765e7cb4c49b21fe883a1907f") throw new Exception("Unrecognized USB backend fingerprint");
            if(Hash(Path.Combine(root,"Comm","UsbHub","RtHub_USB2I2C.dll"))!="1fa6235d6a00c139ed2827c4a6f0de382796b5435a788b4bf1b3e38bfa032a7d") throw new Exception("Unrecognized lower bridge fingerprint");
            Directory.SetCurrentDirectory(root); SetDllDirectory(Path.Combine(root,"Comm"));
            SetCurWorkingPath(root.TrimEnd('\\'));
            SetSettingFilePath(Path.Combine(root,"IspSetting.ini"));
            Console.WriteLine("SOC READ BENCH {0:o}; logical read requests only",DateTime.UtcNow);
            WindowsDdc();
            Initiallize(); Console.WriteLine("Comm modules={0}",GetCommCount());
            int select=SetCommByID(6); Console.WriteLine("SetCommByID(6)=0x{0:X8}; active={1}",select,GetCommID());
            if(select!=0||GetCommID()!=6) return 2;
            PointerMap();
            Console.WriteLine("Devices before open={0}",GetDeviceCount());
            int init=InitialDev(); Console.WriteLine("InitialDev=0x{0:X8} win32={1}",init,Marshal.GetLastWin32Error()); if(init!=0) return 2;
            try {
                // Do not enumerate after opening the bridge.
                Console.WriteLine("DebugMode={0}; debug=0x{1:X2}; isp=0x{2:X2}; continuous=0x{3:X2}",GetDebugMode(),GetDebugSlave(),GetIspSlave(),GetIspContinuousSlave());
                PointerMap();
                if(args[0]!="--ddc-only") {
                    EdidTest("I2CRead/EDID",delegate(IntPtr p){return I2CRead(0xA0,0,128,p);});
                    EdidTest("I2CReadEx/EDID",delegate(IntPtr p){return I2CReadEx(0xA0,0,128,p,1);});
                }

                DdcTest("I2CReadEx/VCP10",delegate(IntPtr p){return I2CReadEx(0x6E,0,11,p,0);});
                DdcTest("DDCCIRead/VCP10",delegate(IntPtr p){return DDCCIRead(0x6E,0,11,p);});
                Console.WriteLine("SOC=UNRESOLVED; XDATA=UNVALIDATED; no snapshot sweep performed.");
            } finally {Console.WriteLine("ReleaseDev=0x{0:X8}",ReleaseDev());}
            return 0;
        } catch(Exception e) {Console.Error.WriteLine(e.GetType().Name+": "+e.Message);return 1;}
    }
}

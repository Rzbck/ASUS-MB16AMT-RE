// Persistent read-only battery telemetry watcher through the verified ASUS
// GET FE/EF/F0 proxy. Campaign mode additionally sets verified VCP 10/ED,
// with restoration. No DataFlash, debug, ISP, reset or arbitrary writes.
using System;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Threading;

static class GaugeWatch {
    const string ExpectedWinComm = "d237f4fbe3ab3acfc4170558785b422aeaea055627522510105f5517b0d78739";
    const string ExpectedBackend = "90f61a228eb4c58dfca72e597e5366549483022765e7cb4c49b21fe883a1907f";
    const string ExpectedLower = "1fa6235d6a00c139ed2827c4a6f0de382796b5435a788b4bf1b3e38bfa032a7d";
    const int TransportRetries = 3;
    const int MaxConsecutiveSampleFailures = 5;
    static volatile bool Stop;

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
    [DllImport("WinComm.dll", CallingConvention=CallingConvention.Cdecl)] static extern int I2CReadEx(byte slave, byte sub, ushort length, IntPtr output, int increment);
    [DllImport("WinComm.dll", CallingConvention=CallingConvention.Cdecl)] static extern int DDCCIWrite(byte slave, byte sub, ushort length, byte[] input);

    delegate int Reader(IntPtr output);
    sealed class Sample { public int Rc; public byte[] Bytes; public bool Changed, Guards; }

    static Sample Read(int capacity, byte fill, Reader reader) {
        IntPtr memory=Marshal.AllocHGlobal(capacity+32);
        try {
            for(int i=0;i<capacity+32;i++) Marshal.WriteByte(memory,i,0xD3);
            for(int i=0;i<capacity;i++) Marshal.WriteByte(memory,16+i,fill);
            int rc=reader(IntPtr.Add(memory,16));
            Sample s=new Sample {Rc=rc,Bytes=new byte[capacity],Guards=true};
            Marshal.Copy(IntPtr.Add(memory,16),s.Bytes,0,capacity);
            for(int i=0;i<capacity;i++) if(s.Bytes[i]!=fill) s.Changed=true;
            for(int i=0;i<16;i++) if(Marshal.ReadByte(memory,i)!=0xD3 || Marshal.ReadByte(memory,16+capacity+i)!=0xD3) s.Guards=false;
            if(!s.Guards) throw new InvalidOperationException("Output guard overwritten; aborting.");
            return s;
        } finally { Marshal.FreeHGlobal(memory); }
    }

    static string Hash(string path) {
        using(var h=SHA256.Create()) using(var f=File.OpenRead(path))
            return BitConverter.ToString(h.ComputeHash(f)).Replace("-","").ToLowerInvariant();
    }
    static ushort U16(byte[] b,int o) { return (ushort)(b[o] | (b[o+1]<<8)); }
    static short S16(byte[] b,int o) { return unchecked((short)U16(b,o)); }

    static bool Vcp10(byte[] b) {
        if(b.Length<11 || b[0]!=0x6E || b[1]!=0x88 || b[2]!=2 || b[3]!=0 || b[4]!=0x10) return false;
        int checksum=0x50; for(int i=0;i<11;i++) checksum^=b[i];
        return checksum==0;
    }
    static bool ProxyFrame4(byte[] b) {
        if(b.Length<7 || b[0]!=0x6E || b[1]!=0x84) return false;
        int checksum=0x50; for(int i=0;i<7;i++) checksum^=b[i];
        if(checksum!=0) return false;
        if(b[2]==0x02 && b[3]==0x00 && b[4]==0x10 && b[5]==0x00) return false;
        return true;
    }
    static string Head(byte[] b,int count) {
        return BitConverter.ToString(b,0,Math.Min(count,b.Length));
    }

    // The verified FE proxy can return stale TX data when its internal I2C read
    // fails. Keep the brightness GET as a known marker before every gauge read,
    // but tolerate bounded transient DDC timing failures instead of terminating
    // the whole watch on the first bad frame.
    static void PrimeBrightness() {
        string last="none";
        for(int attempt=1;attempt<=TransportRetries;attempt++) {
            int rc=DDCCIWrite(0x6E,0x51,2,new byte[]{1,0x10});
            if(rc!=0) {
                last="write_rc=0x"+rc.ToString("X8");
                Console.WriteLine("GAUGE_WATCH_RETRY stage=control_write attempt={0}/{1} {2}",attempt,TransportRetries,last);
                Thread.Sleep(180);
                continue;
            }
            Thread.Sleep(120);
            Sample s=Read(32,0xA5,delegate(IntPtr p){return I2CReadEx(0x6E,0,11,p,0);});
            if(s.Rc==0 && s.Changed && Vcp10(s.Bytes)) return;
            last="read_rc=0x"+s.Rc.ToString("X8")+" changed="+s.Changed+" frame="+Head(s.Bytes,11);
            Console.WriteLine("GAUGE_WATCH_RETRY stage=control_read attempt={0}/{1} {2}",attempt,TransportRetries,last);
            Thread.Sleep(180);
        }
        throw new Exception("Brightness control remained invalid after retries: "+last);
    }

    static byte[] ProxyRead4(byte reg) {
        string last="none";
        for(int attempt=1;attempt<=TransportRetries;attempt++) {
            PrimeBrightness();
            byte[] query={1,0xFE,0xEF,0xF0,0,reg,4};
            int rc=DDCCIWrite(0x6E,0x51,(ushort)query.Length,query);
            if(rc!=0) {
                last="write_rc=0x"+rc.ToString("X8");
                Console.WriteLine("GAUGE_WATCH_RETRY stage=gauge_write reg=0x{0:X2} attempt={1}/{2} {3}",reg,attempt,TransportRetries,last);
                Thread.Sleep(200);
                continue;
            }
            Thread.Sleep(170);
            Sample s=Read(32,0x5A,delegate(IntPtr p){return I2CReadEx(0x6E,0,7,p,0);});
            if(s.Rc==0 && s.Changed && ProxyFrame4(s.Bytes)) {
                byte[] payload=new byte[4]; Array.Copy(s.Bytes,2,payload,0,4); return payload;
            }
            last="read_rc=0x"+s.Rc.ToString("X8")+" changed="+s.Changed+" frame="+Head(s.Bytes,7);
            Console.WriteLine("GAUGE_WATCH_RETRY stage=gauge_read reg=0x{0:X2} attempt={1}/{2} {3}",reg,attempt,TransportRetries,last);
            Thread.Sleep(200);
        }
        throw new Exception("Gauge proxy remained invalid at 0x"+reg.ToString("X2")+" after retries: "+last);
    }

    static int BatteryCurve(uint x) {
        if(x<550) return 0;
        if(x<2950) return (int)((((x-550)*29/24)+100)/100);
        if(x<8050) return (int)((((x-2950)*56/51)+2999)/100);
        if(x<9450) return (int)((x+550)/100);
        return x<=10000?100:255;
    }

    static string Phase="observe";
    static void OneSample() {
        Stopwatch sw=Stopwatch.StartNew();
        byte[] p06=ProxyRead4(0x06); ushort temp=U16(p06,0), volt=U16(p06,2);
        byte[] p10=ProxyRead4(0x10); ushort rm=U16(p10,0), fcc=U16(p10,2);
        byte[] p12=ProxyRead4(0x12); ushort fcc2=U16(p12,0); short current=S16(p12,2);
        byte[] p22=ProxyRead4(0x22); short avgPower=S16(p22,2);
        byte[] p2A=ProxyRead4(0x2A); ushort cycles=U16(p2A,0), soc=U16(p2A,2);
        sw.Stop();
        if(fcc!=fcc2) throw new Exception("FCC changed inside one watch sample; refusing mixed snapshot.");
        uint ratio=fcc==0?65535:((uint)rm*10000/(uint)fcc)&65535;
        int asus=fcc==0?255:BatteryCurve(ratio);
        double tempC=temp/10.0-273.15;
        double vi=(double)volt*(double)current/1000000.0;
        double gaugePower=(double)avgPower/100.0; // bq27541 profile: 10 mW units
        string flow=current<0?"DISCHARGING":current>0?"CHARGING":"NEAR_ZERO";
        string asusText=asus<=100?asus.ToString():"INVALID";
        Console.WriteLine(
            "GAUGE_WATCH {0:HH:mm:ss.fff} V_mV={1} I_mA={2} VI_W={3} AP_W={4} flow={5} RM_mAh={6} FCC_mAh={7} SOC_pct={8} ASUS_pct={9} TEMP_C={10} CYCLES={11} sample_ms={12} phase={13}",
            DateTime.Now,volt,current,vi.ToString("F3",CultureInfo.InvariantCulture),gaugePower.ToString("F3",CultureInfo.InvariantCulture),flow,
            rm,fcc,soc,asusText,tempC.ToString("F2",CultureInfo.InvariantCulture),cycles,sw.ElapsedMilliseconds,Phase);
        if(tempC>45 || volt<3400 || volt>4400) throw new Exception("Campaign telemetry limit reached; restore controls");
    }

    static ushort GetVcp(byte code) {
        for(int attempt=0;attempt<3;attempt++) {
            int rc=DDCCIWrite(0x6E,0x51,2,new byte[]{1,code});Thread.Sleep(150);
            Sample sample=Read(32,0xA5,delegate(IntPtr p){return I2CReadEx(0x6E,0,11,p,0);});
            byte[] b=sample.Bytes;int checksum=0x50;for(int i=0;i<11;i++)checksum^=b[i];
            if(rc==0&&sample.Rc==0&&b[0]==0x6E&&b[1]==0x88&&b[2]==2&&b[3]==0&&b[4]==code&&checksum==0)return (ushort)((b[8]<<8)|b[9]);
            Thread.Sleep(200);
        }throw new Exception("VCP read failed "+code.ToString("X2"));
    }
    static void SetKnownVcp(byte code,ushort value) {
        if((code!=0x10&&code!=0xED)||(code==0x10&&value>100)||(code==0xED&&value>1))throw new Exception("Control outside allowed experiment");
        int rc=DDCCIWrite(0x6E,0x51,4,new byte[]{3,code,(byte)(value>>8),(byte)value});
        if(rc!=0)throw new Exception("Set control failed");Thread.Sleep(400);
        if(GetVcp(code)!=value)throw new Exception("Control readback mismatch");
        Console.WriteLine("CONTROL {0:o} vcp={1:X2} value={2}",DateTime.UtcNow,code,value);
    }
    static void Campaign() {
        ushort originalBrightness=GetVcp(0x10),originalEd=GetVcp(0xED);
        if(originalBrightness>100||originalEd>1)throw new Exception("Unexpected original settings");
        Console.WriteLine("RESTORE_PLAN brightness={0} ED={1}",originalBrightness,originalEd);
        try {
            int[] brightness={100,100,100,75,50,25,0,100};
            int[] policy={0,1,0,0,0,0,0,0};
            for(int phase=0;phase<brightness.Length&&!Stop;phase++) {
                SetKnownVcp(0xED,(ushort)policy[phase]);SetKnownVcp(0x10,(ushort)brightness[phase]);
                Phase="p"+phase+"_b"+brightness[phase]+"_ed"+policy[phase];
                Console.WriteLine("PHASE_START {0:o} phase={1} duration_s={2}",DateTime.UtcNow,Phase,phase==1?75:45);
                Stopwatch hold=Stopwatch.StartNew();
                while(!Stop&&hold.Elapsed.TotalSeconds<(phase==1?75:45)){OneSample();Thread.Sleep(600);}
            }
        } finally {
            // Attempt both restores even if the first one fails.
            Exception restoreError=null;
            try{SetKnownVcp(0x10,originalBrightness);}catch(Exception e){restoreError=e;}
            try{SetKnownVcp(0xED,originalEd);}catch(Exception e){restoreError=e;}
            if(restoreError!=null)throw new Exception("RESTORE_FAILED: "+restoreError.Message);
            Console.WriteLine("RESTORE_CONFIRMED brightness={0} ED={1}",originalBrightness,originalEd);
        }
    }
    static void SelfTest() {
        byte[] x={0x56,0x1A,0xD2,0xFD};
        if(U16(x,0)!=6742 || S16(x,2)!=-558) throw new Exception("decode self-test failed");
        byte[] frame={0x6E,0x84,0x56,0x1A,0x56,0x1A,0xBA};
        if(!ProxyFrame4(frame)) throw new Exception("proxy fixture failed");
        if(BatteryCurve(8610)!=91) throw new Exception("ASUS curve fixture failed");
        Console.WriteLine("GAUGE_WATCH_SELF_TEST_PASS: decode, proxy validation, ASUS curve. No DLL loaded.");
    }

    static int Main(string[] args) {
        try {
            if(args.Length==1 && args[0]=="--self-test") { SelfTest(); return 0; }
            bool restoreOnly=args.Length==3 && args[0]=="--restore-controls";
            if(!restoreOnly && ((args.Length!=1 && args.Length!=2) || (args[0]!="--watch" && args[0]!="--campaign"))) { Console.WriteLine("GaugeWatch --watch [sample-count] | --campaign | --self-test"); return args.Length==0?0:2; }
            int sampleLimit=args.Length==2?int.Parse(args[1],CultureInfo.InvariantCulture):0;
            if(sampleLimit<0 || sampleLimit>10000) throw new Exception("Invalid sample count");
            if(IntPtr.Size!=4) throw new Exception("x86 host required");
            if(!new WindowsPrincipal(WindowsIdentity.GetCurrent()).IsInRole(WindowsBuiltInRole.Administrator)) throw new Exception("Run elevated: vendor bridge initialization requires administrator rights.");
            string root=AppDomain.CurrentDomain.BaseDirectory;
            if(Hash(Path.Combine(root,"WinComm.dll"))!=ExpectedWinComm) throw new Exception("Unrecognized WinComm.dll fingerprint");
            if(Hash(Path.Combine(root,"Comm","Comm_UsbHubI2C.dll"))!=ExpectedBackend) throw new Exception("Unrecognized USB backend fingerprint");
            if(Hash(Path.Combine(root,"Comm","UsbHub","RtHub_USB2I2C.dll"))!=ExpectedLower) throw new Exception("Unrecognized lower bridge fingerprint");
            Directory.SetCurrentDirectory(root); SetDllDirectory(Path.Combine(root,"Comm"));
            SetCurWorkingPath(root.TrimEnd('\\')); SetSettingFilePath(Path.Combine(root,"IspSetting.ini"));
            Console.CancelKeyPress += delegate(object sender, ConsoleCancelEventArgs e) { e.Cancel=true; Stop=true; };
            Console.WriteLine("GAUGE WATCH {0:o}; persistent bridge; mode={1}; ASUS FE GET telemetry; Ctrl+C to stop",DateTime.UtcNow,args[0]);
            Initiallize(); Console.WriteLine("Comm modules={0}",GetCommCount());
            int select=SetCommByID(6); Console.WriteLine("SetCommByID(6)=0x{0:X8}; active={1}",select,GetCommID());
            if(select!=0 || GetCommID()!=6) return 2;
            Console.WriteLine("Devices before open={0}",GetDeviceCount());
            int init=InitialDev(); Console.WriteLine("InitialDev=0x{0:X8}",init); if(init!=0) return 2;
            try {
                if(restoreOnly) {SetKnownVcp(0x10,ushort.Parse(args[1]));SetKnownVcp(0xED,ushort.Parse(args[2]));Console.WriteLine("RESTORE_CONFIRMED brightness={0} ED={1}",args[1],args[2]);return 0;}
                if(args[0]=="--campaign") {Campaign();return 0;}
                int consecutiveFailures=0;
                int samples=0;
                while(!Stop && (sampleLimit==0 || samples<sampleLimit)) {
                    try {
                        OneSample();
                        samples++;
                        consecutiveFailures=0;
                    } catch(Exception sampleError) {
                        consecutiveFailures++;
                        Console.WriteLine("GAUGE_WATCH_WARN sample_failed={0}/{1} message={2}",consecutiveFailures,MaxConsecutiveSampleFailures,sampleError.Message);
                        if(consecutiveFailures>=MaxConsecutiveSampleFailures) throw;
                        Thread.Sleep(600);
                    }
                    for(int i=0;i<6 && !Stop;i++) Thread.Sleep(100);
                }
            } finally { Console.WriteLine("ReleaseDev=0x{0:X8}",ReleaseDev()); }
            return 0;
        } catch(Exception e) { Console.Error.WriteLine(e.GetType().Name+": "+e.Message); return 1; }
    }
}

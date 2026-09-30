// Read-only survey of the internal battery gauge through the already-verified
// ASUS GET FE/EF/F0 proxy. Only bq27541-family STANDARD READ commands are used.
// No Control(), DataFlash, SET VCP, debug, ISP, reset or programming operation.
using System;
using System.IO;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Threading;

static class GaugeSurvey {
    const string ExpectedWinComm = "d237f4fbe3ab3acfc4170558785b422aeaea055627522510105f5517b0d78739";
    const string ExpectedBackend = "90f61a228eb4c58dfca72e597e5366549483022765e7cb4c49b21fe883a1907f";
    const string ExpectedLower = "1fa6235d6a00c139ed2827c4a6f0de382796b5435a788b4bf1b3e38bfa032a7d";

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
    sealed class Sample {
        public int Rc; public byte[] Bytes; public bool Changed, Guards; public long Milliseconds;
    }

    static Sample Read(int capacity, byte fill, Reader reader) {
        IntPtr memory=Marshal.AllocHGlobal(capacity+32);
        try {
            for(int i=0;i<capacity+32;i++) Marshal.WriteByte(memory,i,0xD3);
            for(int i=0;i<capacity;i++) Marshal.WriteByte(memory,16+i,fill);
            Stopwatch sw=Stopwatch.StartNew(); int rc=reader(IntPtr.Add(memory,16)); sw.Stop();
            Sample s=new Sample {Rc=rc,Bytes=new byte[capacity],Guards=true,Milliseconds=sw.ElapsedMilliseconds};
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
        // Exact stale payload reproduced when the internal I2C read fails after
        // priming the TX buffer with GET VCP 0x10.
        if(b[2]==0x02 && b[3]==0x00 && b[4]==0x10 && b[5]==0x00) return false;
        return true;
    }

    static void PrimeBrightness() {
        int rc=DDCCIWrite(0x6E,0x51,2,new byte[]{1,0x10});
        if(rc!=0) throw new Exception("Brightness control request failed: 0x"+rc.ToString("X8"));
        Thread.Sleep(100);
        Sample s=Read(32,0xA5,delegate(IntPtr p){return I2CReadEx(0x6E,0,11,p,0);});
        if(s.Rc!=0 || !s.Changed || !Vcp10(s.Bytes)) throw new Exception("Brightness control reply invalid; refusing gauge survey.");
    }

    static byte[] ProxyRead4(byte reg) {
        PrimeBrightness();
        byte[] query={1,0xFE,0xEF,0xF0,0,reg,4};
        int rc=DDCCIWrite(0x6E,0x51,(ushort)query.Length,query);
        if(rc!=0) throw new Exception("Gauge proxy request failed at 0x"+reg.ToString("X2")+": 0x"+rc.ToString("X8"));
        Thread.Sleep(150);
        Sample s=Read(32,0x5A,delegate(IntPtr p){return I2CReadEx(0x6E,0,7,p,0);});
        bool valid=s.Rc==0 && s.Changed && ProxyFrame4(s.Bytes);
        Console.WriteLine("GAUGE_BLOCK reg=0x{0:X2} rc=0x{1:X8} valid={2} ms={3} frame={4}",reg,s.Rc,valid,s.Milliseconds,BitConverter.ToString(s.Bytes,0,7));
        if(!valid) throw new Exception("Invalid/stale gauge proxy response at register 0x"+reg.ToString("X2"));
        byte[] payload=new byte[4]; Array.Copy(s.Bytes,2,payload,0,4); return payload;
    }

    static int BatteryCurve(uint x) {
        if(x<550) return 0;
        if(x<2950) return (int)((((x-550)*29/24)+100)/100);
        if(x<8050) return (int)((((x-2950)*56/51)+2999)/100);
        if(x<9450) return (int)((x+550)/100);
        return x<=10000?100:255;
    }

    static string Minutes(ushort v) { return v==65535 ? "N/A" : v.ToString()+"min"; }

    static void Survey() {
        Console.WriteLine("GAUGE_SURVEY_MODE=READ_ONLY_STANDARD_COMMANDS");
        Console.WriteLine("PROFILE_CANDIDATE=TI_bq27541_family; identity_not_yet_proven");

        // 0x10/0x12 is the already-verified ASUS battery source. Use it as an anchor.
        byte[] anchor=ProxyRead4(0x10);
        ushort rmAnchor=U16(anchor,0), fccAnchor=U16(anchor,2);
        uint ratio=fccAnchor==0?65535:((uint)rmAnchor*10000/(uint)fccAnchor)&65535;
        int asusTarget=fccAnchor==0?255:BatteryCurve(ratio);
        Console.WriteLine("GAUGE_ANCHOR RM_mAh_candidate={0} FCC_mAh_candidate={1} ratio_bp={2} asus_raw_target_pct={3}",rmAnchor,fccAnchor,ratio,asusTarget<=100?asusTarget.ToString():"INVALID");

        byte[] p06=ProxyRead4(0x06); ushort temp=U16(p06,0), volt=U16(p06,2);
        double tempC=temp/10.0-273.15;
        Console.WriteLine("GAUGE TEMP_raw_0p1K={0} TEMP_C={1:F2} VOLT_mV={2}",temp,tempC,volt);

        byte[] p0A=ProxyRead4(0x0A); ushort flags=U16(p0A,0), nac=U16(p0A,2);
        Console.WriteLine("GAUGE FLAGS=0x{0:X4} NAC_mAh={1}",flags,nac);

        byte[] p0E=ProxyRead4(0x0E); ushort fac=U16(p0E,0), rm=U16(p0E,2);
        Console.WriteLine("GAUGE FAC_mAh={0} RM_mAh={1}",fac,rm);

        byte[] p12=ProxyRead4(0x12); ushort fcc=U16(p12,0); short avgCurrent=S16(p12,2);
        Console.WriteLine("GAUGE FCC_mAh={0} AVG_CURRENT_mA={1}",fcc,avgCurrent);

        byte[] p16=ProxyRead4(0x16); ushort tte=U16(p16,0), ttf=U16(p16,2);
        Console.WriteLine("GAUGE TTE={0} TTF={1}",Minutes(tte),Minutes(ttf));

        byte[] p1A=ProxyRead4(0x1A); short standby=S16(p1A,0); ushort stte=U16(p1A,2);
        Console.WriteLine("GAUGE STANDBY_CURRENT_mA={0} STANDBY_TTE={1}",standby,Minutes(stte));

        byte[] p1E=ProxyRead4(0x1E); short maxLoad=S16(p1E,0); ushort mltte=U16(p1E,2);
        Console.WriteLine("GAUGE MAX_LOAD_CURRENT_mA={0} MAX_LOAD_TTE={1}",maxLoad,Minutes(mltte));

        byte[] p22=ProxyRead4(0x22); ushort availEnergy=U16(p22,0); short avgPower=S16(p22,2);
        Console.WriteLine("GAUGE AVAILABLE_ENERGY_raw={0} AVG_POWER_raw_signed={1}",availEnergy,avgPower);

        byte[] p26=ProxyRead4(0x26); ushort ttecp=U16(p26,0), intTemp=U16(p26,2);
        Console.WriteLine("GAUGE TTE_CONST_POWER={0} INTERNAL_TEMP_C={1:F2}",Minutes(ttecp),intTemp/10.0-273.15);

        byte[] p2A=ProxyRead4(0x2A); ushort cycles=U16(p2A,0), gaugeSoc=U16(p2A,2);
        Console.WriteLine("GAUGE CYCLE_COUNT={0} GAUGE_SOC_pct={1}",cycles,gaugeSoc);

        bool cross=(rm==rmAnchor && fcc==fccAnchor);
        bool plausible=(volt>=2500 && volt<=5000 && temp>=2500 && temp<=3500 && gaugeSoc<=100);
        string evidence=(cross && plausible)?"STRONG_MAP_MATCH":"PARTIAL_MAP_MATCH";
        double batteryPower=(double)volt*(double)avgCurrent/1000000.0;
        string flow=avgCurrent<0?"DISCHARGING":avgCurrent>0?"CHARGING":"NEAR_ZERO";
        Console.WriteLine("GAUGE_PROFILE_EVIDENCE={0}; exact_chip_identity=UNPROVEN",evidence);
        Console.WriteLine("GAUGE_SUMMARY voltage_mV={0} avg_current_mA={1} battery_power_est_W={2:F3} flow={3} RM_mAh={4} FCC_mAh={5} gauge_soc_pct={6} asus_raw_target_pct={7}",volt,avgCurrent,batteryPower,flow,rmAnchor,fccAnchor,gaugeSoc,asusTarget<=100?asusTarget.ToString():"INVALID");
        Console.WriteLine("NOTE: negative AverageCurrent means discharge for the bq27541 command convention; positive means charge.");
    }

    static void SelfTest() {
        byte[] x={0x56,0x1A,0x70,0xFE};
        if(U16(x,0)!=6742 || S16(x,2)!=-400) throw new Exception("LE16/signed decode self-test failed");
        byte[] frame={0x6E,0x84,0x56,0x1A,0x56,0x1A,0xBA};
        if(!ProxyFrame4(frame)) throw new Exception("Proxy positive fixture failed");
        byte[] stale={0x6E,0x84,0x02,0x00,0x10,0x00,0xA8};
        if(ProxyFrame4(stale)) throw new Exception("Stale proxy fixture accepted");
        if(BatteryCurve(9433)!=99 || BatteryCurve(10000)!=100) throw new Exception("Battery curve self-test failed");
        Console.WriteLine("GAUGE_SELF_TEST_PASS: decode, checksum/stale rejection, ASUS curve. No DLL loaded.");
    }

    static int Main(string[] args) {
        try {
            if(args.Length==1 && args[0]=="--self-test") { SelfTest(); return 0; }
            if(args.Length!=1 || args[0]!="--gauge-survey") {
                Console.WriteLine("GaugeSurvey --gauge-survey | --self-test"); return args.Length==0?0:2;
            }
            if(IntPtr.Size!=4) throw new Exception("x86 host required");
            if(!new WindowsPrincipal(WindowsIdentity.GetCurrent()).IsInRole(WindowsBuiltInRole.Administrator)) throw new Exception("Run elevated: vendor bridge initialization requires administrator rights.");
            string root=AppDomain.CurrentDomain.BaseDirectory;
            if(Hash(Path.Combine(root,"WinComm.dll"))!=ExpectedWinComm) throw new Exception("Unrecognized WinComm.dll fingerprint");
            if(Hash(Path.Combine(root,"Comm","Comm_UsbHubI2C.dll"))!=ExpectedBackend) throw new Exception("Unrecognized USB backend fingerprint");
            if(Hash(Path.Combine(root,"Comm","UsbHub","RtHub_USB2I2C.dll"))!=ExpectedLower) throw new Exception("Unrecognized lower bridge fingerprint");
            Directory.SetCurrentDirectory(root); SetDllDirectory(Path.Combine(root,"Comm"));
            SetCurWorkingPath(root.TrimEnd('\\')); SetSettingFilePath(Path.Combine(root,"IspSetting.ini"));
            Console.WriteLine("GAUGE SURVEY {0:o}; ASUS FE GET only; standard read-only gauge commands",DateTime.UtcNow);
            Initiallize(); Console.WriteLine("Comm modules={0}",GetCommCount());
            int select=SetCommByID(6); Console.WriteLine("SetCommByID(6)=0x{0:X8}; active={1}",select,GetCommID());
            if(select!=0 || GetCommID()!=6) return 2;
            Console.WriteLine("Devices before open={0}",GetDeviceCount());
            int init=InitialDev(); Console.WriteLine("InitialDev=0x{0:X8}",init); if(init!=0) return 2;
            try { Survey(); }
            finally { Console.WriteLine("ReleaseDev=0x{0:X8}",ReleaseDev()); }
            return 0;
        } catch(Exception e) { Console.Error.WriteLine(e.GetType().Name+": "+e.Message); return 1; }
    }
}

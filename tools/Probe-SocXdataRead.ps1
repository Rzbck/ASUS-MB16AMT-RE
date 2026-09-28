param(
    [string]$FirmwareRoot = "$env:TEMP\MB16AMT_RE\fw"
)

$ErrorActionPreference = 'Stop'

Write-Host 'ASUS MB16AMT — read-only SOC XDATA capability probe'
Write-Host 'NO WRITES; tests only whether ReadMcuReg can distinguish 16-bit addresses.'

$winComm = Get-ChildItem -Path $FirmwareRoot -Filter WinComm.dll -Recurse -File | Select-Object -First 1
if (-not $winComm) { throw "WinComm.dll not found under $FirmwareRoot" }
$root = $winComm.Directory.FullName
$commDir = Join-Path $FirmwareRoot 'Comm'
if (-not (Test-Path $commDir)) { $commDir = $root }

$csc = "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\csc.exe"
if (-not (Test-Path $csc)) { throw "x86 csc.exe not found: $csc" }

$src = Join-Path $env:TEMP 'MB16_SocXdataProbe.cs'
$exe = Join-Path $root 'MB16_SocXdataProbe.exe'

$code = @'
using System;
using System.IO;
using System.Runtime.InteropServices;

class Native {
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode)]
    public static extern bool SetDllDirectory(string lpPathName);

    [DllImport("WinComm.dll", CallingConvention=CallingConvention.Cdecl)]
    public static extern void Initiallize();

    [DllImport("WinComm.dll", CallingConvention=CallingConvention.Cdecl)]
    public static extern int SetCommByID(int id);

    [DllImport("WinComm.dll", CallingConvention=CallingConvention.Cdecl)]
    public static extern int InitialDev();

    [DllImport("WinComm.dll", CallingConvention=CallingConvention.Cdecl)]
    public static extern int ReleaseDev();

    [DllImport("WinComm.dll", CallingConvention=CallingConvention.Cdecl)]
    public static extern byte GetDeviceCount();

    [DllImport("WinComm.dll", CallingConvention=CallingConvention.Cdecl)]
    public static extern byte GetDebugMode();

    [DllImport("WinComm.dll", CallingConvention=CallingConvention.Cdecl)]
    public static extern byte GetIspSlave();

    [DllImport("WinComm.dll", CallingConvention=CallingConvention.Cdecl)]
    public static extern byte GetIspContinuousSlave();

    [DllImport("WinComm.dll", CallingConvention=CallingConvention.Cdecl)]
    public static extern byte GetDebugSlave();

    // Signature previously used by the project. Read-only.
    [DllImport("WinComm.dll", CallingConvention=CallingConvention.Cdecl)]
    public static extern int ReadMcuReg(uint address, out byte value);
}

class Program {
    static void Main(string[] args) {
        string root = args[0];
        string comm = args[1];
        Directory.SetCurrentDirectory(root);
        Native.SetDllDirectory(comm);

        Native.Initiallize();
        int rcSet = Native.SetCommByID(6);
        int rcInit = Native.InitialDev();
        Console.WriteLine("SetCommByID(6)=0x{0:X}", rcSet);
        Console.WriteLine("InitialDev=0x{0:X}", rcInit);
        Console.WriteLine("Devices={0}", Native.GetDeviceCount());
        try {
            Console.WriteLine("DebugMode={0} ISP=0x{1:X2} continuous=0x{2:X2} debug=0x{3:X2}",
                Native.GetDebugMode(), Native.GetIspSlave(), Native.GetIspContinuousSlave(), Native.GetDebugSlave());
        } catch (EntryPointNotFoundException) {
            Console.WriteLine("Debug getters unavailable in this WinComm build; continuing.");
        }

        uint[] low =  { 0x33u, 0x34u, 0x35u, 0x36u };
        uint[] high = { 0xD833u, 0xD834u, 0xD835u, 0xD836u };

        Console.WriteLine();
        Console.WriteLine("===== LOW vs HIGH ADDRESS TEST =====");
        bool allSame = true;
        for (int pass=0; pass<3; pass++) {
            Console.WriteLine("-- pass {0} --", pass + 1);
            for (int i=0; i<low.Length; i++) {
                byte vl=0, vh=0;
                int rl = Native.ReadMcuReg(low[i], out vl);
                int rh = Native.ReadMcuReg(high[i], out vh);
                bool same = (rl == rh && vl == vh);
                if (!same) allSame = false;
                Console.WriteLine("0x{0:X4}: rc=0x{1:X8} val=0x{2:X2}   |   0x{3:X4}: rc=0x{4:X8} val=0x{5:X2}   {6}",
                    low[i], rl, vl, high[i], rh, vh, same ? "SAME" : "DIFF");
            }
        }

        Console.WriteLine();
        Console.WriteLine("===== RESULT =====");
        if (allSame) {
            Console.WriteLine("All high addresses alias their low-byte counterparts across all passes.");
            Console.WriteLine("Conclusion: ReadMcuReg is not proving 16-bit XDATA access here; do NOT use it for a D8xx SOC scan.");
        } else {
            Console.WriteLine("At least one high address differs from its low-byte counterpart.");
            Console.WriteLine("Conclusion: 16-bit addressing may be available; next step is a narrow runtime monitor, not a broad sweep.");
        }

        int rcRel = Native.ReleaseDev();
        Console.WriteLine("ReleaseDev=0x{0:X}", rcRel);
    }
}
'@

Set-Content -LiteralPath $src -Value $code -Encoding UTF8

& $csc /nologo /platform:x86 /out:$exe $src
if ($LASTEXITCODE -ne 0) { throw "C# compile failed: $LASTEXITCODE" }

& $exe $root $commDir
if ($LASTEXITCODE -ne 0) { throw "Probe host exited with code $LASTEXITCODE" }

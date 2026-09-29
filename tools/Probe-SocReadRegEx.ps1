param(
    [string]$FirmwareRoot = "$env:TEMP\MB16AMT_RE\fw"
)

$ErrorActionPreference = 'Stop'

throw 'Retired: ReadRegEx can write register/page selectors and D8xx is not proven XDATA. Use Run-SocReadBench.ps1 for validated transport reads. See docs/LIVE_READ_BENCH.md.'

Write-Host 'ASUS MB16AMT — narrow ReadRegEx XDATA probe'
Write-Host 'READ-ONLY: no register writes, no firmware writes, no ISP programming.'

$winComm = Get-ChildItem -Path $FirmwareRoot -Filter WinComm.dll -Recurse -File | Select-Object -First 1
if (-not $winComm) { throw "WinComm.dll not found under $FirmwareRoot" }
$root = $winComm.Directory.FullName
$commDir = Join-Path $FirmwareRoot 'Comm'
if (-not (Test-Path $commDir)) { $commDir = $root }

$csc = "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\csc.exe"
if (-not (Test-Path $csc)) { throw "x86 csc.exe not found: $csc" }

$src = Join-Path $env:TEMP 'MB16_SocReadRegExProbe.cs'
$exe = Join-Path $root 'MB16_SocReadRegExProbe.exe'

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

    // Offline x86 inspection shows two stack args: full address at [EBP+08]
    // and a pointer-like second arg at [EBP+0C]. Read-only probe only.
    [DllImport("WinComm.dll", CallingConvention=CallingConvention.Cdecl)]
    public static extern int ReadRegEx(uint address, out byte value);
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

        uint[] addrs = {
            0xFF33u, // MCU-register-space control address
            0xD833u, 0xD834u, 0xD835u, 0xD836u, // prior generic OSD scratch area
            0xD9FFu, // known firmware state byte from static analysis
            0xDA69u, // known generic dirty/update state byte
            0xD823u  // known state byte used by nearby OSD/control code
        };

        Console.WriteLine();
        Console.WriteLine("===== ReadRegEx read-only samples =====");
        bool anyZeroRc = false;
        bool anyNonZeroValue = false;
        for (int pass = 0; pass < 3; pass++) {
            Console.WriteLine("-- pass {0} --", pass + 1);
            foreach (uint addr in addrs) {
                byte value = 0xA5;
                int rc = Native.ReadRegEx(addr, out value);
                if (rc == 0) anyZeroRc = true;
                if (value != 0) anyNonZeroValue = true;
                Console.WriteLine("0x{0:X4}: rc=0x{1:X8} val=0x{2:X2}", addr, rc, value);
            }
        }

        Console.WriteLine();
        Console.WriteLine("===== RESULT =====");
        if (anyZeroRc) {
            Console.WriteLine("At least one ReadRegEx call returned rc=0. This is consistent with a usable read primitive.");
            Console.WriteLine("Do not infer SOC from these addresses yet; next step is correlation only after validating the returned bytes.");
        } else {
            Console.WriteLine("No ReadRegEx call returned rc=0. Stop: do not scan memory with this signature.");
        }
        Console.WriteLine("Any non-zero returned byte: {0}", anyNonZeroValue ? "yes" : "no");

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

param(
    [string]$FirmwareRoot = "$env:TEMP\MB16AMT_RE\fw",
    [string]$OutputRoot = "$env:TEMP\MB16AMT_RE\read-bench",
    [switch]$Run
)
$ErrorActionPreference = 'Stop'
if (-not $Run) {
    Write-Host 'Use -Run from an elevated PowerShell to validate fixed EDID / GET VCP reads.'
    Write-Host 'No SOC claim, memory sweep, SET VCP, debug switch or programming operation.'
    return
}
$principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Vendor bridge initialization requires an elevated PowerShell.'
}
$root = (Resolve-Path -LiteralPath $FirmwareRoot).Path
# Every run uses a fresh host directory; preserve the vendor dependency tree.
$hostDir = Join-Path $OutputRoot (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
New-Item -ItemType Directory -Path $hostDir -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $root 'WinComm.dll') -Destination $hostDir
Copy-Item -LiteralPath (Join-Path $root 'Comm') -Destination $hostDir -Recurse
$source = Join-Path $PSScriptRoot 'SocReadBench.cs'
$exe = Join-Path $hostDir 'SocReadBench.exe'
$compiler = "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\csc.exe"
& $compiler /nologo /platform:x86 "/out:$exe" $source
if ($LASTEXITCODE -ne 0) { throw 'Read bench compilation failed.' }
& $exe --self-test
if ($LASTEXITCODE -ne 0) { throw 'Read bench self-test failed.' }
$stdout = Join-Path $hostDir 'stdout.txt'
$stderr = Join-Path $hostDir 'stderr.txt'
$process = Start-Process -FilePath $exe -ArgumentList '--run' -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
if (-not $process.WaitForExit(60000)) {
    $process.Kill()
    throw "Read bench exceeded 60 seconds; host stopped. Local log: $stdout"
}
$process.WaitForExit()
Get-Content -LiteralPath $stdout
Get-Content -LiteralPath $stderr
if ($process.ExitCode -ne 0) { throw "Read bench failed: $($process.ExitCode)" }
Write-Host "Local report: $stdout"

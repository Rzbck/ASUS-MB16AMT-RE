param(
    [string]$FirmwareRoot = "$env:TEMP\MB16AMT_RE\fw",
    [string]$OutputRoot = "$env:TEMP\MB16AMT_RE\read-bench"
)
$ErrorActionPreference = 'Stop'

$principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Vendor bridge initialization requires an elevated PowerShell.'
}

$root = (Resolve-Path -LiteralPath $FirmwareRoot).Path
$hostDir = Join-Path $OutputRoot (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
New-Item -ItemType Directory -Path $hostDir -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $root 'WinComm.dll') -Destination $hostDir
Copy-Item -LiteralPath (Join-Path $root 'Comm') -Destination $hostDir -Recurse

$source = Join-Path $PSScriptRoot 'GaugeWatch.cs'
$exe = Join-Path $hostDir 'GaugeWatch.exe'
$compiler = "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\csc.exe"
& $compiler /nologo /platform:x86 "/out:$exe" $source
if ($LASTEXITCODE -ne 0) { throw 'Gauge watch compilation failed.' }

& $exe --self-test
if ($LASTEXITCODE -ne 0) { throw 'Gauge watch self-test failed.' }

Write-Host 'Starting persistent read-only gauge watch. Ctrl+C to stop.' -ForegroundColor Cyan
Write-Host 'Change monitor brightness/load while it runs and watch I_mA / AP_W react.' -ForegroundColor Cyan
& $exe --watch
if ($LASTEXITCODE -ne 0) { throw "Gauge watch failed: $LASTEXITCODE" }

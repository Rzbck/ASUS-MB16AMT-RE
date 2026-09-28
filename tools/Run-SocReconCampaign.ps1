param(
    [string]$FirmwareRoot = "$env:TEMP\MB16AMT_RE\fw",
    [string]$ReportRoot = "$env:TEMP\MB16AMT_RE\reports"
)

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$Py = Join-Path $RepoRoot 'tools\soc_recon_campaign.py'
if (-not (Test-Path $Py)) { throw "Missing campaign script: $Py" }
if (-not (Test-Path $FirmwareRoot)) { throw "Firmware root not found: $FirmwareRoot" }

New-Item -ItemType Directory -Force -Path $ReportRoot | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$json = Join-Path $ReportRoot "soc-recon-$stamp.json"
$txt  = Join-Path $ReportRoot "soc-recon-$stamp.txt"

Write-Host '============================================================'
Write-Host ' ASUS MB16AMT — SOC RECON CAMPAIGN'
Write-Host '============================================================'
Write-Host 'Mode: OFFLINE / READ-ONLY'
Write-Host 'No DLL load. No device I/O. No register write. No ISP.'
Write-Host "Firmware root: $FirmwareRoot"
Write-Host "Text report:    $txt"
Write-Host "JSON report:    $json"
Write-Host

$cmdArgs = @(
    $Py,
    $FirmwareRoot,
    '--details',
    '--json', $json
)

# Preserve full output in a report while streaming it live to the terminal.
& python @cmdArgs 2>&1 | Tee-Object -FilePath $txt
$rc = $LASTEXITCODE

Write-Host
Write-Host '============================================================'
if ($rc -eq 0) {
    Write-Host 'CAMPAIGN COMPLETE'
    Write-Host "TXT_REPORT=$txt"
    Write-Host "JSON_REPORT=$json"
} else {
    Write-Host "CAMPAIGN FAILED rc=$rc"
    throw "soc_recon_campaign.py exited with code $rc"
}
Write-Host '============================================================'

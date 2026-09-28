param(
    [string]$FirmwareRoot = "$env:TEMP\MB16AMT_RE\fw",
    [string]$ReportRoot = "$env:TEMP\MB16AMT_RE\reports"
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$Campaign = Join-Path $RepoRoot 'tools\soc_recon_campaign.py'
$Deep = Join-Path $RepoRoot 'tools\soc_recon_deep.py'
if (-not (Test-Path $Campaign)) { throw "Missing campaign script: $Campaign" }
if (-not (Test-Path $Deep)) { throw "Missing deep campaign script: $Deep" }
if (-not (Test-Path $FirmwareRoot)) { throw "Firmware root not found: $FirmwareRoot" }

New-Item -ItemType Directory -Force -Path $ReportRoot | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$json = Join-Path $ReportRoot "soc-recon-$stamp.json"
$deepJson = Join-Path $ReportRoot "soc-recon-deep-$stamp.json"
$txt = Join-Path $ReportRoot "soc-recon-full-$stamp.txt"

Write-Host '============================================================'
Write-Host ' ASUS MB16AMT - FULL SOC RECON CAMPAIGN'
Write-Host '============================================================'
Write-Host 'Mode: OFFLINE / READ-ONLY'
Write-Host 'No DLL load. No device I/O. No register write. No ISP.'
Write-Host 'OUTPUT MODE: FULL TERMINAL'
Write-Host 'The TXT/JSON files are automatic local backups only.'
Write-Host 'You do NOT need to send those files; the useful analysis is printed below.'
Write-Host "Firmware root: $FirmwareRoot"
Write-Host

Write-Host '#################### PASS A - GLOBAL CAMPAIGN ####################'
& python $Campaign $FirmwareRoot '--details' '--json' $json 2>&1 | Tee-Object -FilePath $txt
$rc1 = $LASTEXITCODE
if ($rc1 -ne 0) { throw "soc_recon_campaign.py exited with code $rc1" }

Write-Host
Write-Host '#################### PASS B - DEEP RESOLVER #####################'
& python $Deep $FirmwareRoot '--all-context' '--json' $deepJson 2>&1 | Tee-Object -FilePath $txt -Append
$rc2 = $LASTEXITCODE
if ($rc2 -ne 0) { throw "soc_recon_deep.py exited with code $rc2" }

Write-Host
Write-Host '============================================================'
Write-Host 'FULL CAMPAIGN COMPLETE'
Write-Host 'TERMINAL_OUTPUT_IS_COMPLETE=YES'
Write-Host 'No separate TXT/JSON upload is required.'
Write-Host "BACKUP_TXT=$txt"
Write-Host "BACKUP_JSON=$json"
Write-Host "BACKUP_DEEP_JSON=$deepJson"
Write-Host '============================================================'

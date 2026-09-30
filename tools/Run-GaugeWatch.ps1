param(
 [string]$FirmwareRoot = "$env:TEMP\MB16AMT_RE\fw",
 [string]$OutputRoot = "$env:TEMP\MB16AMT_RE\read-bench",
 [ValidateRange(0,10000)][int]$Samples = 0,
 [switch]$Campaign
)
$ErrorActionPreference='Stop'
$principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Elevated PowerShell required'}
if($Campaign -and $Samples){throw 'Choose Campaign or Samples'}
$root=(Resolve-Path -LiteralPath $FirmwareRoot).Path
$hostDir=Join-Path $OutputRoot (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
New-Item -ItemType Directory -Path $hostDir -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $root 'WinComm.dll') -Destination $hostDir
Copy-Item -LiteralPath (Join-Path $root 'Comm') -Destination $hostDir -Recurse
$source=Join-Path $PSScriptRoot 'GaugeWatch.cs';$exe=Join-Path $hostDir 'GaugeWatch.exe'
& "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\csc.exe" /nologo /platform:x86 "/out:$exe" $source
if($LASTEXITCODE -ne 0){throw 'Compilation failed'}
& $exe --self-test
if($LASTEXITCODE -ne 0){throw 'Self-test failed'}
if(-not $Campaign){& $exe --watch $Samples;if($LASTEXITCODE -ne 0){throw "Watch failed: $LASTEXITCODE"};return}
# Only the documented brightness and ED controls are changed. The native host
# restores in finally; this separate supervisor also restores after host failure.
$stdout=Join-Path $hostDir 'campaign.txt';$stderr=Join-Path $hostDir 'campaign-error.txt'
Write-Output "CAMPAIGN_LOG=$stdout"
$child=Start-Process -FilePath $exe -ArgumentList '--campaign' -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
$watch=[Diagnostics.Stopwatch]::StartNew();$shown=0
try {
 while(-not $child.WaitForExit(1000)){
  if($watch.Elapsed.TotalSeconds -gt 900){Stop-Process -Id $child.Id -Force;throw 'Campaign timed out; restoring controls'}
  if(Test-Path $stdout){$lines=@(Get-Content -LiteralPath $stdout);if($lines.Count -gt $shown){$lines[$shown..($lines.Count-1)];$shown=$lines.Count}}
 }
 $child.WaitForExit()
 $lines=@(Get-Content -LiteralPath $stdout);if($lines.Count -gt $shown){$lines[$shown..($lines.Count-1)]}
 Get-Content -LiteralPath $stderr
 if($child.ExitCode -ne 0){throw "Campaign host failed: $($child.ExitCode)"}
} finally {
 if(-not $child.HasExited){$child.WaitForExit()}
 $plan=Get-Content -LiteralPath $stdout | Select-String '^RESTORE_PLAN brightness=(\d+) ED=(\d+)$' | Select-Object -First 1
 if($plan){
  $brightness=[int]$plan.Matches[0].Groups[1].Value;$policy=[int]$plan.Matches[0].Groups[2].Value
  if($brightness -gt 100 -or $policy -gt 1){throw 'Invalid restore plan'}
  & $exe --restore-controls $brightness $policy
  if($LASTEXITCODE -ne 0){throw 'Supervisor restore failed; controls need immediate attention'}
 } else {Write-Output 'No restore plan: host did not reach control mutations'}
}

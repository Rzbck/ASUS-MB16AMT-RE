[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$FirmwarePath
)

$ErrorActionPreference = 'Stop'

$ExpectedSize = 0xE0000
$ExpectedSha256 = '1E75681279BF974D2810E6D2ED91AABBEDA35DE3FABE1881733AA8A12319CB0C'
$BankSize = 0x10000

if (-not $FirmwarePath) {
    $root = Join-Path $env:TEMP 'MB16AMT_RE\fw'
    $candidate = Get-ChildItem $root -Recurse -File -Filter '*V020*reduce.bin' -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $candidate) {
        throw "Firmware V020 not found below $root. Pass -FirmwarePath explicitly."
    }
    $FirmwarePath = $candidate.FullName
}

$FirmwarePath = (Resolve-Path $FirmwarePath).Path
$file = Get-Item $FirmwarePath
if ($file.Length -ne $ExpectedSize) {
    throw ('Unexpected firmware size: {0} bytes / 0x{0:X}' -f $file.Length)
}

$actualSha = (Get-FileHash $FirmwarePath -Algorithm SHA256).Hash.ToUpperInvariant()
if ($actualSha -ne $ExpectedSha256) {
    throw "Unexpected SHA256: $actualSha"
}

$fw = [System.IO.File]::ReadAllBytes($FirmwarePath)

function Convert-HexPattern {
    param([string]$Hex)
    return [byte[]]($Hex -split '\s+' | Where-Object { $_ } | ForEach-Object { [Convert]::ToByte($_, 16) })
}

function Find-Pattern {
    param(
        [byte[]]$Data,
        [byte[]]$Pattern
    )

    $hits = New-Object System.Collections.Generic.List[int]
    for ($i = 0; $i -le ($Data.Length - $Pattern.Length); $i++) {
        $ok = $true
        for ($j = 0; $j -lt $Pattern.Length; $j++) {
            if ($Data[$i + $j] -ne $Pattern[$j]) {
                $ok = $false
                break
            }
        }
        if ($ok) { $hits.Add($i) }
    }
    return $hits
}

function Format-Context {
    param(
        [byte[]]$Data,
        [int]$Offset,
        [int]$Before = 16,
        [int]$After = 32
    )

    $start = [Math]::Max(0, $Offset - $Before)
    $end = [Math]::Min($Data.Length - 1, $Offset + $After - 1)
    $bytes = $Data[$start..$end]
    return (($bytes | ForEach-Object { $_.ToString('X2') }) -join ' ')
}

# 8051 MOV DPTR,#imm16 is: 90 high low
# These are the RL6492 bank-switch XDATA registers documented by public source.
$patterns = [ordered]@{
    'MOV_DPTR_FFFC' = '90 FF FC'
    'MOV_DPTR_FFFD' = '90 FF FD'
    'MOV_DPTR_FFFE' = '90 FF FE'
    'MOV_DPTR_FFFF' = '90 FF FF'

    # Public STARTUP.a51 when _STARTUP_SPEED_UP_SUPPORT is enabled:
    # MOV DPTR,#0FFFC; MOVX A,@DPTR; ORL A,#01F; MOVX @DPTR,A;
    # INC DPTR; CLR A; MOVX @DPTR,A; INC DPTR; MOVX @DPTR,A
    'STARTUP_BANK_INIT' = '90 FF FC E0 44 1F F0 A3 E4 F0 A3 F0'
}

Write-Host ''
Write-Host '===== VERIFIED IMAGE ====='
Write-Host "Firmware : $FirmwarePath"
Write-Host "SHA256   : $actualSha"
Write-Host ''
Write-Host '===== RL6492 BANK-SWITCH SIGNATURES ====='

$allRows = @()

foreach ($item in $patterns.GetEnumerator()) {
    $patternBytes = Convert-HexPattern $item.Value
    $hits = Find-Pattern -Data $fw -Pattern $patternBytes

    Write-Host ''
    Write-Host ("--- {0} [{1}] : {2} hit(s) ---" -f $item.Key, $item.Value, $hits.Count)

    foreach ($offset in $hits) {
        $bank = [int][Math]::Floor($offset / $BankSize)
        $local = $offset % $BankSize
        $context = Format-Context -Data $fw -Offset $offset

        $row = [PSCustomObject]@{
            Signature  = $item.Key
            FileOffset = ('0x{0:X6}' -f $offset)
            Bank       = $bank
            Local      = ('0x{0:X4}' -f $local)
            Context    = $context
        }
        $allRows += $row

        Write-Host ("bank={0,2} local=0x{1:X4} file=0x{2:X6}" -f $bank, $local, $offset)
        Write-Host "  $context"
    }
}

$out = Join-Path (Split-Path -Parent $FirmwarePath) 'bank-switch-signatures.csv'
$allRows | Export-Csv -Path $out -NoTypeInformation -Encoding UTF8

Write-Host ''
Write-Host "CSV: $out"
Write-Host 'READ-ONLY: no device communication and no firmware modification.'

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$FirmwarePath,

    [string]$OutputDirectory
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
    throw ('Unexpected firmware size: {0} bytes / 0x{0:X}; expected {1} / 0x{1:X}' -f $file.Length, $ExpectedSize)
}

$actualSha = (Get-FileHash $FirmwarePath -Algorithm SHA256).Hash.ToUpperInvariant()
if ($actualSha -ne $ExpectedSha256) {
    throw "Unexpected SHA256: $actualSha (expected $ExpectedSha256)"
}

if (-not $OutputDirectory) {
    $OutputDirectory = Split-Path -Parent $FirmwarePath
}

$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

$fw = [System.IO.File]::ReadAllBytes($FirmwarePath)
$bankCount = [int]($fw.Length / $BankSize)
$sha256 = [System.Security.Cryptography.SHA256]::Create()

$standardVectors = [ordered]@{
    RESET  = 0x0000
    INT0   = 0x0003
    TIMER0 = 0x000B
    INT1   = 0x0013
    TIMER1 = 0x001B
    SERIAL = 0x0023
    TIMER2 = 0x002B
}

function Format-HexBytes {
    param(
        [byte[]]$Bytes
    )

    return (($Bytes | ForEach-Object { $_.ToString('X2') }) -join ' ')
}

function Decode-VectorCandidate {
    param(
        [byte]$B0,
        [byte]$B1,
        [byte]$B2
    )

    # Explicit [int] promotion is required before shifting. Without it,
    # PowerShell can lose the high byte when values originate as System.Byte.
    $target = (([int]$B1 -shl 8) -bor [int]$B2)

    switch ([int]$B0) {
        0x02 { return ('LJMP 0x{0:X4}' -f $target) }
        0x12 { return ('LCALL 0x{0:X4}' -f $target) }
        0x22 { return 'RET' }
        0x32 { return 'RETI' }
        default { return ('raw {0:X2} {1:X2} {2:X2}' -f $B0, $B1, $B2) }
    }
}

$bankRows = @()
$vectorRows = @()

for ($bank = 0; $bank -lt $bankCount; $bank++) {
    $base = $bank * $BankSize
    $chunk = New-Object byte[] $BankSize
    [Array]::Copy($fw, $base, $chunk, 0, $BankSize)

    $hash = [Convert]::ToHexString($sha256.ComputeHash($chunk))

    $zeroCount = 0
    $ffCount = 0
    $byte02Count = 0
    $byte12Count = 0

    foreach ($x in $chunk) {
        if ($x -eq 0x00) { $zeroCount++ }
        if ($x -eq 0xFF) { $ffCount++ }
        if ($x -eq 0x02) { $byte02Count++ }
        if ($x -eq 0x12) { $byte12Count++ }
    }

    $bankRows += [PSCustomObject]@{
        Bank         = $bank
        FileOffset   = ('0x{0:X6}' -f $base)
        ZeroBytes    = $zeroCount
        FFBytes      = $ffCount
        Byte_02      = $byte02Count
        Byte_12      = $byte12Count
        SHA256       = $hash
        First32Bytes = Format-HexBytes -Bytes $chunk[0..31]
    }

    foreach ($entry in $standardVectors.GetEnumerator()) {
        $local = [int]$entry.Value
        $p = $base + $local
        $b0 = $fw[$p]
        $b1 = $fw[$p + 1]
        $b2 = $fw[$p + 2]

        $vectorRows += [PSCustomObject]@{
            Bank       = $bank
            Vector     = $entry.Key
            Local      = ('0x{0:X4}' -f $local)
            FileOffset = ('0x{0:X6}' -f $p)
            Raw        = ('{0:X2} {1:X2} {2:X2}' -f $b0, $b1, $b2)
            Decode     = Decode-VectorCandidate -B0 $b0 -B1 $b1 -B2 $b2
        }
    }
}

$bankCsv = Join-Path $OutputDirectory 'static-bank-map.csv'
$vectorCsv = Join-Path $OutputDirectory 'static-vector-map.csv'
$summaryTxt = Join-Path $OutputDirectory 'static-map-summary.txt'

$bankRows | Export-Csv -Path $bankCsv -NoTypeInformation -Encoding UTF8
$vectorRows | Export-Csv -Path $vectorCsv -NoTypeInformation -Encoding UTF8

$summary = New-Object System.Collections.Generic.List[string]
$summary.Add('ASUS MB16AMT / RL6492 V020 static map')
$summary.Add("Firmware: $FirmwarePath")
$summary.Add("Size: $($file.Length) bytes / 0x$($file.Length.ToString('X'))")
$summary.Add("SHA256: $actualSha")
$summary.Add("Banks: $bankCount x 0x$($BankSize.ToString('X'))")
$summary.Add('')
$summary.Add('BANK MAP')
$summary.Add(($bankRows | Format-Table Bank, FileOffset, ZeroBytes, FFBytes, Byte_02, Byte_12 -AutoSize | Out-String).TrimEnd())
$summary.Add('')
$summary.Add('VECTOR MAP')
$summary.Add(($vectorRows | Format-Table Bank, Vector, Local, Raw, Decode -AutoSize | Out-String).TrimEnd())
$summary.Add('')
$summary.Add('FIRST 32 BYTES')
foreach ($row in $bankRows) {
    $summary.Add(('BANK {0}: {1}' -f $row.Bank, $row.First32Bytes))
}

$summary | Set-Content -Path $summaryTxt -Encoding UTF8

Write-Host ''
Write-Host '===== VERIFIED IMAGE ====='
Write-Host "Firmware : $FirmwarePath"
Write-Host "Size     : $($file.Length) bytes / 0x$($file.Length.ToString('X'))"
Write-Host "SHA256   : $actualSha"
Write-Host ''
Write-Host '===== BANK MAP ====='
$bankRows | Format-Table Bank, FileOffset, ZeroBytes, FFBytes, Byte_02, Byte_12 -AutoSize
Write-Host ''
Write-Host '===== CORRECTED VECTOR MAP ====='
$vectorRows | Format-Table Bank, Vector, Local, Raw, Decode -AutoSize
Write-Host ''
Write-Host 'Generated:'
Write-Host "  $bankCsv"
Write-Host "  $vectorCsv"
Write-Host "  $summaryTxt"
Write-Host ''
Write-Host 'READ-ONLY: this script never communicates with the monitor and never modifies the firmware image.'

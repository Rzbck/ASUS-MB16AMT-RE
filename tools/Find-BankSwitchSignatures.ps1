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

function Test-BytesAt {
    param(
        [byte[]]$Data,
        [int]$Offset,
        [byte[]]$Pattern
    )

    if ($Offset -lt 0 -or ($Offset + $Pattern.Length) -gt $Data.Length) {
        return $false
    }

    for ($i = 0; $i -lt $Pattern.Length; $i++) {
        if ($Data[$Offset + $i] -ne $Pattern[$i]) {
            return $false
        }
    }
    return $true
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
    return (($Data[$start..$end] | ForEach-Object { $_.ToString('X2') }) -join ' ')
}

Write-Host ''
Write-Host '===== VERIFIED IMAGE ====='
Write-Host "Firmware : $FirmwarePath"
Write-Host "SHA256   : $actualSha"

# Bank-control register accesses.
$registerPatterns = [ordered]@{
    'MOV_DPTR_FFFC' = '90 FF FC'
    'MOV_DPTR_FFFD' = '90 FF FD'
    'MOV_DPTR_FFFE' = '90 FF FE'
    'MOV_DPTR_FFFF' = '90 FF FF'
}

Write-Host ''
Write-Host '===== BANK REGISTER ACCESS COUNTS ====='
foreach ($item in $registerPatterns.GetEnumerator()) {
    $hits = Find-Pattern -Data $fw -Pattern (Convert-HexPattern $item.Value)
    Write-Host ('{0,-15} {1,4}' -f $item.Key, $hits.Count)
}

# Public STARTUP.a51 form and the actual compiler form observed in ASUS V020.
$startupPublic = Convert-HexPattern '90 FF FC E0 44 1F F0 A3 E4 F0 A3 F0'
$startupAsus   = Convert-HexPattern '90 FF FC E0 44 1F F0 E4 90 FF FD F0 90 FF FE F0'

$publicHits = Find-Pattern -Data $fw -Pattern $startupPublic
$asusHits = Find-Pattern -Data $fw -Pattern $startupAsus

Write-Host ''
Write-Host '===== STARTUP BANK INIT ====='
Write-Host "Public A3 form hits : $($publicHits.Count)"
Write-Host "ASUS compiled hits  : $($asusHits.Count)"
foreach ($offset in $asusHits) {
    $bank = [int][Math]::Floor($offset / $BankSize)
    $local = $offset % $BankSize
    Write-Host ('ASUS startup: bank={0} local=0x{1:X4} file=0x{2:X6}' -f $bank, $local, $offset)
    Write-Host ('  ' + (Format-Context -Data $fw -Offset $offset -Before 24 -After 48))
}

# Classify all MOV DPTR,#FFFF occurrences.
$ffffPattern = Convert-HexPattern '90 FF FF'
$ffffHits = Find-Pattern -Data $fw -Pattern $ffffPattern

$rows = @()
$selectorRows = @()
$otherRows = @()

foreach ($offset in $ffffHits) {
    $bank = [int][Math]::Floor($offset / $BankSize)
    $local = $offset % $BankSize
    $category = 'Other'
    $selector = $null

    # Selector table is local 0x2603 + N*0x10 and has:
    # F8 74 NN 90 FF FF F5 44 F0 E8 22
    if ($local -ge 0x2603 -and $local -le 0x26F3 -and (($local - 0x2603) % 0x10) -eq 0) {
        $n = [int](($local - 0x2603) / 0x10)
        $expected = [byte[]](0xF8, 0x74, $n, 0x90, 0xFF, 0xFF, 0xF5, 0x44, 0xF0, 0xE8, 0x22)
        if (Test-BytesAt -Data $fw -Offset ($offset - 3) -Pattern $expected) {
            $category = 'SelectorStub'
            $selector = $n
        }
    }

    if ($category -ne 'SelectorStub') {
        $next = if (($offset + 3) -lt $fw.Length) { $fw[$offset + 3] } else { 0 }
        switch ($next) {
            0xE0 { $category = 'ReadCurrentBank' } # MOVX A,@DPTR
            0xF0 { $category = 'WriteCurrentA' }   # MOVX @DPTR,A
            default { $category = ('Other_next_{0:X2}' -f $next) }
        }
    }

    $row = [PSCustomObject]@{
        Bank       = $bank
        Local      = ('0x{0:X4}' -f $local)
        FileOffset = ('0x{0:X6}' -f $offset)
        Category   = $category
        Selector   = if ($null -eq $selector) { '' } else { ('0x{0:X2}' -f $selector) }
        Next8      = (($fw[$offset..([Math]::Min($fw.Length - 1, $offset + 10))] | ForEach-Object { $_.ToString('X2') }) -join ' ')
        Context    = Format-Context -Data $fw -Offset $offset
    }

    $rows += $row
    if ($category -eq 'SelectorStub') { $selectorRows += $row } else { $otherRows += $row }
}

Write-Host ''
Write-Host '===== PBANK 0xFFFF SUMMARY ====='
Write-Host "Total MOV DPTR,#FFFF : $($rows.Count)"
Write-Host "Selector stubs       : $($selectorRows.Count)"
Write-Host "Other accesses       : $($otherRows.Count)"

Write-Host ''
Write-Host 'Selector stubs per physical bank:'
$selectorRows | Group-Object Bank | Sort-Object { [int]$_.Name } | ForEach-Object {
    Write-Host ('  bank {0,2}: {1}' -f $_.Name, $_.Count)
}

Write-Host ''
Write-Host 'Non-table access categories:'
$otherRows | Group-Object Category | Sort-Object Name | ForEach-Object {
    Write-Host ('  {0,-24} {1,3}' -f $_.Name, $_.Count)
}

Write-Host ''
Write-Host '===== NON-TABLE 0xFFFF ACCESSES ====='
$otherRows | Sort-Object Bank, Local | Format-Table Bank, Local, FileOffset, Category, Next8 -AutoSize

# Count direct LCALL references to the selector table addresses.
Write-Host ''
Write-Host '===== DIRECT LCALLS TO SELECTOR STUBS ====='
$callRows = @()
for ($n = 0; $n -lt 16; $n++) {
    $target = 0x2603 + ($n * 0x10)
    $hi = ($target -shr 8) -band 0xFF
    $lo = $target -band 0xFF
    $callPattern = [byte[]](0x12, $hi, $lo)
    $calls = Find-Pattern -Data $fw -Pattern $callPattern

    $callRows += [PSCustomObject]@{
        Selector = ('0x{0:X2}' -f $n)
        Target   = ('0x{0:X4}' -f $target)
        LCALLs   = $calls.Count
    }
}
$callRows | Format-Table -AutoSize

$outDir = Split-Path -Parent $FirmwarePath
$rows | Export-Csv -Path (Join-Path $outDir 'bank-switch-all.csv') -NoTypeInformation -Encoding UTF8
$otherRows | Export-Csv -Path (Join-Path $outDir 'bank-switch-nontable.csv') -NoTypeInformation -Encoding UTF8
$callRows | Export-Csv -Path (Join-Path $outDir 'bank-switch-lcalls.csv') -NoTypeInformation -Encoding UTF8

Write-Host ''
Write-Host "CSV all      : $(Join-Path $outDir 'bank-switch-all.csv')"
Write-Host "CSV non-table: $(Join-Path $outDir 'bank-switch-nontable.csv')"
Write-Host "CSV LCALL    : $(Join-Path $outDir 'bank-switch-lcalls.csv')"
Write-Host 'READ-ONLY: no device communication and no firmware modification.'

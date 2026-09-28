# Static firmware map — ASUS MB16AMT V020

This document is the incremental static-analysis map for the ASUS MB16AMT RL6492 firmware.

The goal is to accumulate only reproducible facts and clearly labeled hypotheses until the OSD, battery/SOC, charging, power-management, and eventually safe firmware-modification paths are understood.

## Reference image

```text
file: ASUS_RL6492_MB16AMT_Project_AUO_B156HAK02_FF000_20211227_V020_4D38_ELot5_reduce.bin
size: 917504 bytes = 0xE0000
SHA256: 1E75681279BF974D2810E6D2ED91AABBEDA35DE3FABE1881733AA8A12319CB0C
```

The image divides exactly into:

```text
14 banks × 0x10000 bytes = 0xE0000 bytes
```

No proprietary firmware bytes are committed to this repository. This file records only derived metadata and analysis.

## Bank inventory

Initial read-only analysis of the known V020 image produced the following map.

> Important: `0x02 bytes` and `0x12 bytes` below are raw byte-frequency counts only. On 8051, `0x02` and `0x12` are opcodes for `LJMP` and `LCALL` when encountered in decoded code, but the current counts also include occurrences inside operands/data. They must **not** be treated as instruction counts.

| Bank | File offset | Zero bytes | FF bytes | `0x02` bytes | `0x12` bytes | SHA256 |
|---:|---:|---:|---:|---:|---:|---|
| 0 | `0x000000` | 16391 | 1325 | 1220 | 885 | `7E13AD95A6FBAEC77FC155BF473FCD0DC0A47108350E6C3FA64778DD51623419` |
| 1 | `0x010000` | 3744 | 4350 | 1242 | 1038 | `7A7CD6AA81D22B9B3739A33241A557134F7E316E558EC09C039C51EA8729CC72` |
| 2 | `0x020000` | 25557 | 1133 | 1267 | 856 | `5922ACAB1A0DDED0A39779A8E982A0B2F8F47946DC016E429A842A09FC0F0E44` |
| 3 | `0x030000` | 9699 | 1286 | 1276 | 1567 | `E23B855A45E28014CE0F9EAFD5A5C4974ED0A04AF302739E2BB9B143EEF3B9AC` |
| 4 | `0x040000` | 12300 | 1299 | 1512 | 587 | `272D12F88B6428ECC1BFDED2BB54C702F33D9F03B0AF2D70ECDD0648B5C402FB` |
| 5 | `0x050000` | 17717 | 1311 | 1546 | 1587 | `E1C154C13E217F28FD976743243BB2B6FD14AF076CFFEFBC86B10A95DB3FC117` |
| 6 | `0x060000` | 3549 | 1876 | 2809 | 3257 | `D0D120906A26B1A124CC73F0AD0F543429CE8B2401A93352E697E97FCE0735C5` |
| 7 | `0x070000` | 1831 | 1685 | 2060 | 3035 | `D6DA29278EE3132D65755CF1983FAC1C7546394DCFCF29D1DF567B51155BC269` |
| 8 | `0x080000` | 2274 | 1998 | 1971 | 3957 | `EC171FCB30020F307ABC198A2BF85CFB234AFB111C5B3AC0E2C7EC217B684874` |
| 9 | `0x090000` | 3932 | 1824 | 1695 | 2711 | `65DC7F8FF2C116F1627886D448D251679BAEBD051366F449FA1E6B102CC1F6C6` |
| 10 | `0x0A0000` | 7442 | 1388 | 1508 | 2456 | `AF09FE37DC78682F722F389AB72FF2F2149D5C64369E97AD07256904D51519FF` |
| 11 | `0x0B0000` | 25456 | 1120 | 1158 | 413 | `36ABA279E5D57B2D8E4F7C0720FE1ECEEE111B115D90B143719885B979AACE50` |
| 12 | `0x0C0000` | 17584 | 1193 | 1380 | 709 | `8107992B82592B7D71DB163F75930D5E882A5CBC16901835FCD5AD420DA30D37` |
| 13 | `0x0D0000` | 500 | 39835 | 1065 | 778 | `954650F84BE7814222C5CE487CDF93842AD7225AF1C6C698F85BFB389D4F9962` |

### Immediate structural observations

These are safe observations from the byte distribution, not yet semantic assignments:

- banks 6–10 are comparatively dense in non-zero/non-`FF` content and also contain many raw `0x12` bytes;
- banks 2 and 11 contain large zero-filled regions;
- bank 13 is structurally different from most other banks, with `39835` bytes equal to `0xFF` and only `500` zero bytes;
- every bank has a different SHA256, so none of the complete 64 KiB banks is byte-identical to another.

Do not yet label any bank as "OSD", "battery", "tables", "boot", etc. Those assignments require control-flow/data-flow evidence.

## Repeated 8051 vector/trampoline page

The first 32 bytes are **identical in all 14 banks**:

```text
02 2A 27 02 2B 48 22 FF FF FF FF 02 00 4E FF FF
FF FF FF 02 2C 29 FF FF FF FF FF 02 00 C7 FF FF
```

This is strong evidence that the 64 KiB banks share a common 8051-style vector/trampoline layout at their local address `0x0000`.

From the raw bytes, the currently reliable vector candidates in the first 32 bytes are:

```text
local 0x0000: 02 2A 27  -> LJMP 0x2A27
local 0x0003: 02 2B 48  -> LJMP 0x2B48
local 0x000B: 02 00 4E  -> LJMP 0x004E
local 0x0013: 02 2C 29  -> LJMP 0x2C29
local 0x001B: 02 00 C7  -> LJMP 0x00C7
```

The raw bytes for the later vector locations (`0x0023`, `0x002B`, etc.) must be re-extracted with the corrected parser before their targets are recorded here.

### Interpretation status

The fact that the same vector bytes appear at the start of every physical 64 KiB block is important, but the precise bank-switching model is not yet proven.

Working hypotheses to test:

1. each flash bank is independently mapped into the same 16-bit 8051 code window;
2. some low-address routines are intentionally duplicated in each bank to provide common entry/vector behavior;
3. far/banked calls likely use a Realtek-specific bank selector/trampoline convention that must be identified before cross-bank call graphs are trusted.

These are hypotheses, not conclusions.

## Parser correction discovered during first run

The first PowerShell vector parser produced outputs such as:

```text
02 2A 27 -> LJMP 0x0027
02 2B 48 -> LJMP 0x0048
02 2C 29 -> LJMP 0x0029
```

Those displayed targets are wrong. The high byte was lost during the shift/or expression because the source values were handled as `System.Byte` values.

For future parsing, promote the bytes to an integer before shifting, for example:

```powershell
$target = (([int]$b1 -shl 8) -bor [int]$b2)
```

Therefore:

```text
02 2A 27 -> 0x2A27
02 2B 48 -> 0x2B48
02 2C 29 -> 0x2C29
```

Any first-run vector target that was based only on the buggy computed display must be treated as unverified until its raw bytes are re-read.

## Why this matters for the battery/OSD path

The primary RE target remains the battery percentage displayed by the OSD.

The public RL6492 reference tree contains generic numeric OSD-rendering paths such as `OsdPropShowNumber(...)`. The next static-analysis phase should locate analogous compiled formatting/rendering routines in the ASUS image and enumerate callers, rather than guessing battery I2C addresses at runtime.

Desired chain:

```text
OSD numeric rendering
        <- caller displaying 0..100
        <- battery/SOC state update
        <- conversion / threshold logic
        <- internal ADC / I2C / PMIC / gauge read
```

The known external VCP `0xED` charge-policy control should later be cross-referenced against the same internal power-management code because it provides one already proven bridge between Windows-visible behavior and ASUS battery/charging logic.

## Safety status

This phase is entirely static/read-only.

No monitor command, ISP entry, flash write, erase, reset, or modified-firmware operation is required for the bank mapping work.

Do not move to modified-firmware flashing until all of the following are independently understood:

- running-firmware dump/recovery path;
- bank selection and boot semantics;
- checksum/signature layout;
- hardware/panel revision match;
- recovery behavior after a failed image.

## Next static tasks

1. re-run vector extraction with integer-safe target decoding and capture raw bytes around all standard/extended vector locations;
2. determine the actual RL6492 bank-switch/far-call convention from public source and compiled patterns;
3. identify real code boundaries rather than raw opcode-byte frequencies;
4. find high-confidence common-library signatures from the public RL6492 source;
5. search for the compiled numeric OSD renderer and build its caller graph;
6. trace the first plausible 0..100 battery/SOC path backward to its hardware read primitive.

Update this file incrementally as each claim moves from hypothesis to reproducible evidence.

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

The fact that the same vector bytes appear at the start of every physical 64 KiB block is important, but the precise bank-switching model is not yet proven for the ASUS build.

Working hypotheses to test:

1. each flash bank is independently mapped into the same 16-bit 8051 code window;
2. some low-address routines are intentionally duplicated in each bank to provide common entry/vector behavior;
3. far/banked calls use a Realtek bank-selector/trampoline convention that must be identified before cross-bank call graphs are trusted.

These are hypotheses about the ASUS image, not conclusions.

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

## RL6492 bank-switch architecture from public reference source

The public RL6492 source gives a concrete hardware model to correlate against the ASUS image.

RL6492 defines four XDATA registers at the top of the 16-bit address space:

```text
0xFFFC  MCU_FFFC_BANK_SWICH_CONTROL
0xFFFD  MCU_FFFD_XDATA_BANK_START
0xFFFE  MCU_FFFE_XDATA_BANK_SEL
0xFFFF  MCU_FFFF_PBANK_SWITCH
```

The Realtek startup assembly explicitly enables address remapping / global XRAM / XFR and states that it uses `Pbank_switch` to enable bank switching. It accesses `0xFFFC` and then initializes the following bank-related registers.

Public system code also changes the active program bank by assigning a bank value directly to:

```c
MCU_FFFF_PBANK_SWITCH = ucBankAddress;
```

and the public global macro for reading the current bank is based on the same register.

### Consequence for ASUS V020 analysis

This does **not** prove the ASUS build uses the reference source unchanged, but it strongly narrows what to search for in compiled code:

- `MOV DPTR,#0xFFFC` / accesses around XDATA `FFFC..FFFF`;
- code that writes a bank number to XDATA `0xFFFF` immediately before/after a cross-bank transition;
- startup sequences matching the public `STARTUP.a51` register initialization;
- repeated low-address vector code that may be common precisely because multiple physical banks are mapped into a shared 16-bit code address space.

This is now the preferred route for reconstructing cross-bank control flow. Do not assume physical file offset `bank*0x10000 + local_address` is sufficient to resolve every call until the `Pbank_switch` convention in the ASUS build is identified.

## Confirmed ASUS V020 bank-switch implementation

A targeted read-only scan of the ASUS V020 image found `251` raw occurrences of:

```text
90 FF FF
```

which is 8051 `MOV DPTR,#0xFFFF` when decoded as code.

### Repeated 16-entry bank selector table

Of those 251 hits, **224 are explained by one repeated structure**:

```text
16 selector stubs × 14 physical 64 KiB banks = 224 occurrences
```

Every physical bank contains selector stubs at the same local addresses:

```text
0x2603
0x2613
0x2623
...
0x26F3
```

The immediate bank numbers run from `0x00` through `0x0F`.

Representative stub for bank `N`:

```text
F8 74 NN 90 FF FF F5 44 F0 E8 22
```

8051 decoding:

```asm
MOV  R0,A
MOV  A,#NN
MOV  DPTR,#0xFFFF
MOV  0x44,A
MOVX @DPTR,A
MOV  A,R0
RET
```

This is high-confidence evidence for a program-bank selection helper:

- it writes the selected bank number to `MCU_FFFF_PBANK_SWITCH` (`XDATA 0xFFFF`);
- it also mirrors that number into internal direct RAM address `0x44`;
- it preserves accumulator `A` across the operation;
- the helpers are laid out at fixed `0x10`-byte spacing;
- a full generic selector table for banks `0x00..0x0F` is present even though the package image itself contains 14 physical 64 KiB blocks.

Because the exact same selector table exists in all 14 blocks, the earlier hypothesis that each physical bank is mapped into a shared 16-bit code window is now strongly supported.

The remaining `27` occurrences of `90 FF FF` are outside this repeated selector table. They are distributed across multiple banks and include apparent reads of the current bank (`90 FF FF E0`) plus other call/control-flow contexts. They remain to be classified individually before assigning semantics.

### ASUS startup bank/XDATA initialization

A second high-confidence match exists in physical bank 0 at local offset `0x6381`.

Observed bytes:

```text
90 FF FC E0 44 1F F0 E4 90 FF FD F0 90 FF FE F0
```

8051 interpretation:

```asm
MOV  DPTR,#0xFFFC
MOVX A,@DPTR
ORL  A,#0x1F
MOVX @DPTR,A
CLR  A
MOV  DPTR,#0xFFFD
MOVX @DPTR,A
MOV  DPTR,#0xFFFE
MOVX @DPTR,A
```

This closely matches the public Realtek `STARTUP.a51` semantics:

1. enable address remapping / XRAM / XFR and bank-switching through `0xFFFC` with mask `0x1F`;
2. initialize `XDATA_BANK_START` at `0xFFFD` to zero;
3. initialize `XDATA_BANK_SEL` at `0xFFFE` to zero.

An earlier exact-byte signature expected the public assembly's `INC DPTR` (`A3`) encoding between these register accesses and therefore returned zero hits. That negative result is **not** evidence against the match: the ASUS binary reloads `DPTR` explicitly with `90 FF FD` and `90 FF FE` while implementing the same register-level operation.

### Current bank-model confidence

The following are now considered **confirmed for the ASUS V020 binary**, not merely inferred from public source:

- code uses XDATA `0xFFFF` as a bank-selection register;
- bank selector helpers exist for logical bank numbers `0x00..0x0F`;
- the selector helper writes both `0xFFFF` and direct RAM `0x44`;
- the same selector table is duplicated in every physical 64 KiB block;
- startup code in physical bank 0 initializes the RL6492 banking/XDATA control registers `0xFFFC..0xFFFE` with semantics matching the Realtek reference architecture.

What is **not yet proven**:

- which logical bank number maps to each meaningful functional module;
- whether every package bank `0..13` maps one-to-one to selector values `0..13` under all boot/partition states;
- the role of selector values `0x0E` and `0x0F` when only 14 physical package banks are present;
- whether direct RAM `0x44` is only a software mirror/current-bank cache or has additional linker/runtime semantics;
- the exact far-call ABI used by application code around these selector stubs.

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

1. classify the 27 non-table accesses to `0xFFFF` as reads, writes, or banked-call helpers;
2. map callers/references to the repeated selector table at `0x2603..0x26F3`;
3. identify the exact far-call ABI and return-to-previous-bank behavior;
4. identify real code boundaries rather than raw opcode-byte frequencies;
5. find high-confidence common-library signatures from the public RL6492 source;
6. search for the compiled numeric OSD renderer and build its caller graph;
7. trace the first plausible 0..100 battery/SOC path backward to its hardware read primitive.

Update this file incrementally as each claim moves from hypothesis to reproducible evidence.

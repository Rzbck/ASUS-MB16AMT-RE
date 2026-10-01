# Static firmware map — ASUS MB16AMT V020

**CONFIRMED event02 fixture completion:** [OSD_EVENTS.md](OSD_EVENTS.md) verifies 37 original whole paths under explicit early-wait/delay/error-polling snapshots and65,536 wait arguments. Timer11/08 requests, retained language/dirty and cleared menu/gate/event are checked. Opcode82 now has1,024 firmware-free CI checks. Physical success/timing remain unproved; next RAM42:43 clock and RAM36/RAM39 calibration. Full OSD map unfinished.

**97% confirmed live:** three source reads at 07:00:34Z returned 6190/6742 -> x=9181 -> target 97%, matching the user OSD report. Timer setup 5:E268 now matches the reference millisecond routine: nominal acquisition ~1 s and continued filter steps ~13 s (strong evidence, physical timing unmeasured). FE GET dispatch was checked in 65,544 offline cases; remaining cache-read investigation is inside service 12:F684 and diagnostic leaves, not selector guessing. See [BATTERY_LIVE_PROXY.md](BATTERY_LIVE_PROXY.md).

**100% -> 99% live validation:** on 2026-09-30, the user reported OSD 99%; three fresh source samples were 6360/6742, 6359/6742, 6359/6742. The exact firmware curve independently returns **99%** for all three (raw ratios 9433/9431 basis points). Brightness was 100, so it is not the source of this result. See [evidence](BATTERY_LIVE_PROXY.md). Direct DA4C access and transient filter timing remain unresolved. Timer setup is now localized to 5:E268: it sets D988:D989 and the reload bytes D95E/D960; derive its caller arguments and clock selection before assigning a wall-clock duration.

**Live reader follow-up:** the documented wrapper passed a second independent run; six total source samples are 6742/6742 -> raw target 100%. See `maps/battery-live-observations.json`. Next precise work: finish FE GET coverage for a DA4C read route and establish timer divider D988:D989 (ISR 0:011A -> 4:F90A, countdown DA52:DA53 -> 9:BF79). Do not infer exact display timing from 03E8 alone.

**LIVE BREAKTHROUGH 2026-09-30:** ASUS GET FE/EF/F0 reaches internal AA:10 through 12:E431 -> 1508 -> 0:6D00. Three live replies: 6E 84 56 1A 56 1A BA, source words 6742/6742, exact raw target **100%**. Use `tools/Run-SocReadBench.ps1 -Run -BatteryProxy`. See [BATTERY_LIVE_PROXY.md](BATTERY_LIVE_PROXY.md). DA4C itself remains unread; raw target and filtered display can differ during transitions. Earlier no-live-source statements below are historical. Next: establish runtime DA4C exposure through the FE GET handler or another proven read route.

**GET VCP follow-up:** nine vendor branches at 9:A3A0 checked offline (6,912 executions); no DA4C/D9F7/DCC2 read and no battery-dependent reply. The default 9:EC87 -> 1856 -> 13:6628 is a DDC NULL reply, not a memory proxy. Next: trace the RX routing upstream of 9:EC5B and D990 for a separate read handler. See the battery provenance document.

**Follow-up:** D9F7 is a saved copy of DA4C, with one-byte storage offset 02BE and a 0..100 validator (invalid -> 50). All 256 validator inputs pass. The updater also reaches the ED policy evaluator E703 before display/scaler sink 13:3DE6. See `BATTERY_PERCENTAGE.md`. No live read route is established.

## Battery chain verified — 2026-09-30

`I2C AA:10 (4 bytes) -> 0:5A5C -> 0:6EB9 -> DA4C -> 10:F8F4 -> 1:D7A1` is now traced and checked offline. See [exact acquisition, curve, filter, writers and renderer](BATTERY_PERCENTAGE.md) and [verification counts](maps/battery-provenance.json). DA4C is the battery percentage consumed by the OSD; live read access remains unresolved. The alternate renderer explains why the three known 1:EAEB callers were unrelated. Expanded bounded dispatch decoding yields 158,425 instructions / 2,986 thunk edges / 20 unresolved indirect jumps. Earlier graph counts below are historical.

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

The ABI milestone below supersedes tasks 1–3 from the previous session.

1. use the resolved thunk/callsite maps to identify the compiled numeric OSD renderer;
2. resolve indirect dispatch only where it blocks the chosen OSD caller path;
3. trace a plausible 0..100 display value backward to its hardware read primitive;
4. retain the distinction between static reachability, logical banks and physical package offsets.

Update this file incrementally as each claim moves from hypothesis to reproducible evidence.

## 2026-09-28 continuation: banked-call ABI reconstructed

### CONFIRMED — correction to selector entry addresses

The earlier `0x2603 + 0x10*N` addresses identify the **MOV DPTR instruction inside**
each selector. The callable entry is **`S(N) = 0x2600 + 0x10*N`**.
The entire eleven-byte stub previously printed begins at S(N), not S(N)+3.
The older sections above are historical observations; use these corrected entries.

All fourteen banks are identical throughout `[0000,2DC4)` (11,716 bytes);
the first bank-dependent byte is at `2DC4`. This is an image equality boundary,
not proof of a hardware mapping boundary. Both ABI tables are within that prefix.

### CONFIRMED — three layers of the ABI

| Layer | Local addresses | Contents / role |
|---|---|---|
| Function thunks | `0AE8..1C45`, six-byte entries | 741 entries: load callee address into DPTR, LJMP to G(N) |
| Bank call gates | `G(N)=09C2+12h*N`, N=0..15 | 18-byte routines that push restoration address and callee address |
| Bank selectors | `S(N)=2600+10h*N`, N=0..15 | Update RAM 44 and XDATA FFFF, then RET |

Each thunk has the form `MOV DPTR,#callee; LJMP G(N)`. For example:
`0AE8 -> G(4)=0A0A -> logical bank 4, local FB6A`.
All 741 destinations use logical banks 0..13. No thunk targets 14 or 15.
Counts by logical bank 0..13:
`44,18,19,13,84,74,104,83,100,22,38,6,26,110`.

Decoded G(N), with addresses relative to G(N):

```asm
+00 MOV  A,44h          ; previous logical bank
+02 ANL  A,#0Fh
+04 SWAP A             ; low byte of S(previous)
+05 PUSH ACC
+07 MOV  A,#26h        ; high byte of S(previous)
+09 PUSH ACC
+0B PUSH DPL           ; low byte of callee
+0D PUSH DPH           ; high byte of callee
+0F LJMP S(N)
```

On an ordinary LCALL to a thunk, stack contents after the gate (bottom to top):

```text
caller return low, caller return high,
previous-selector low, previous-selector high,
callee low, callee high
```

S(N) switches to N; its RET consumes the callee address. The callee's RET lands
on S(previous), whose RET resumes the original caller. No POP 44 or separate
hardware-register read is needed: the restoration address encodes the old bank.
Same-bank calls use this same path; this gate has no conditional fast path.
An LJMP to a thunk is a tail transfer using the existing caller return address.

RAM `44h` therefore has a demonstrated **current-bank ABI role**, not just an
incidental cache. Each selector updates it before writing XDATA FFFF.
The selector preserves A, but the call gate does not: callee entry A is `26h`.
R0 and DPTR are scratch; DPTR is FFFF after selection. The return selector
preserves the callee's A result. No claim about interrupt timing is made.
Banking adds four transient stack bytes above the caller return, two of which
remain while the callee executes. Nested calls restore each previous bank.

`0AE2` is a separate dynamic selector: `MOV A,R7; SWAP A; MOV DPTR,#2600; JMP @A+DPTR`.
For R7 in 0..15 it enters S(R7). It does not itself push a restoration address.
Do not model a call to this helper as the six-byte thunk ABI.

### STRONG EVIDENCE — public source identity

The ASUS gates and selectors match the `SELECT` and `SWITCH` macros in the
public reference's `Kernel/Common/L51_bank.a51`, XDATA mode / <=16 banks,
without the optional bank-offset call. Snapshot:
`3d38340ec8518a8888fd5d8dbb181c2a7418e11c`.
This corroborates the Keil-style interpretation; it does not identify ASUS's
complete build configuration. See [reference assembly](https://github.com/Kingdomwhisky/RTD-Scaler-TEST/blob/3d38340ec8518a8888fd5d8dbb181c2a7418e11c/Kernel/Common/L51_bank.a51)
and [Keil's mechanism description](https://www.keil.com/support/docs/1059.htm).

### CONFIRMED / STRONG EVIDENCE — all 27 non-table occurrences classified

There are **25 immediate MOVX-read forms and two generic-pointer offsets**.
There is no non-table direct PBANK write in this specific 251-hit inventory.
This does not exclude writes through a computed DPTR elsewhere.

The 25 read-form sites (physical bank in decimal, local addresses in hex):

| Bank | Sites |
|---:|---|
| 0 | 53A0 |
| 1 | D015 |
| 3 | F144 |
| 4 | F225, FB5B, FEB9 |
| 6 | C4D5, ED15, EE33, F996 |
| 7 | 7A36, BEDB, EE54 |
| 9 | B68E |
| 10 | EBB2, EE08, F2FA, F321 |
| 11 | FBEC |
| 12 | F085, F9E2, FA18 |
| 13 | 38B3, 522C, 5FA2 |

24 are on instruction boundaries reached by the current static traversal.
`9:B68E` has the same coherent read/store helper sequence but is not reached;
its code interpretation remains STRONG EVIDENCE, not a runtime observation.
Many store the current bank in XDATA parameter slots such as D83D, D893 or D89A;
these are not the call gate's stack-based restoration mechanism.

At `1:F43D` and `1:F823`, `MOV DPTR,#FFFF` is followed by `LCALL 1D55`.
Helper 1D55 adds DPTR to the generic pointer R2:R1, selecting memory type by R3.
FFFF is **-1 modulo 65536**, used to read the preceding byte. It is not a read
of the bank register. This classification follows the helper's decoded paths,
including MOVC for code pointers; it is not based on the immediate alone.

### DEAD END / NEGATIVE RESULT — direct selector LCALL search

No raw LCALL targets any old `2603+10h*N` address. Searching corrected selector
entries finds just one raw `LCALL 2620` byte pattern, at `7:5CEC`, inside a
data-like region and outside the recovered instruction map. It is not accepted
as a call. The application uses common thunks and LJMP gates instead.

### Reproducible maps and bounded verification

Run the dependency-free script with uv; the input is size/SHA-checked:

```powershell
uv run --no-project tools/analyze_banked_abi.py '<path-to-V020.bin>' --out work/abi
```

Versioned derived results are under `docs/maps/`:

- `bank-thunks.csv`: all 741 thunk -> logical-bank:callee mappings;
- `bank-call-edges.csv`: 2,540 decoded callsite/tail-transfer edges through thunks;
- `bank-nontable.csv`: all 27 occurrences and instruction-boundary evidence;
- `bank-unresolved-indirect.csv`: 54 unresolved indirect-jump contexts;
- `bank-abi-summary.json`: input fingerprint, counts, checks and limits.

The local output additionally includes `bank-raw-references.csv` (4,620 raw
long-transfer matches). Those matches are candidates, not proven calls.
The graph preserves separate physical copies of common callers, includes
same-bank transfers through thunks, and records callsites rather than inferred
function starts. It is a usable **partial** graph, not a complete call graph.

Traversal starts from vector candidates and every thunk destination. It knows
8051 instruction lengths, conditional/direct branches and two decoded helpers:
`20D0` consumes four inline constant bytes; `210D` consumes byte-switch records
`target_hi,target_lo,value`, terminated by `00,00,default_hi,default_lo`.
Treating those payloads as code caused false overlaps; the corrected traversal
has 146,439 instruction starts, zero overlaps and zero reserved A5 opcodes.
These checks improve confidence but do not prove runtime reachability.

The script executes the actual gate/selector instructions in a small bounded
offline model: **10,374 thunk round trips** (741 x 14 starting banks) and
**2,744 nested bank triples** pass, including same-bank calls, stack balance,
mirror restoration and accumulator-result preservation. Function bodies are
stubbed by RET; this is not full hardware emulation or a recovery test.

### HYPOTHESIS / unresolved scope

- Target traversal assumes logical N corresponds to physical package bank N.
  Consistent destinations support this for analysis; boot/partition relocation
  and the exact executing image are still unproven.
- There is no callee-bank offset adjustment in these verified selector stubs.
  This does not rule out every other form of remapping.
- Banks 14/15 have selector slots but no image data or thunk destinations.
- Computed calls, remaining switch forms and dynamic-bank users remain to map.
- No battery/SOC function has yet been identified by this ABI milestone.

No display command, reset, ISP action or firmware mutation was performed.

## 2026-09-28 continuation: numeric OSD renderer candidate

### STRONG EVIDENCE — bank 1:EAEB through common thunk 1670

With the ABI known, a focused decimal-formatting search identifies a strong
`OsdPropShowNumber` analogue at **logical bank 1, EAEB**. This is a derived
functional name, not a recovered ASUS symbol. Public comparison:
[RTD2014OsdFontProp.c, OsdPropShowNumber](https://github.com/Kingdomwhisky/RTD-Scaler-TEST/blob/3d38340ec8518a8888fd5d8dbb181c2a7418e11c/User/RTD%20Series/RTD2014Osd/Code/RTD2014OsdFontProp.c#L1728).

Independent points of correspondence:

- A 32-bit unsigned input is loaded from XDATA `D838..D83B` into R4..R7.
- Helper `1:CF81` loads 100000 into R0..R3; `1:CF89` loads the input and tail
  jumps to the common division routine `1FB9`.
- Subsequent quotients/remainders use divisors 10000 (`1:EB51`), 1000
  (`1:EB69`), 100 (`1:EB81`) and 10 (`1:EB96`). `1:D0D4` moves the remainder
  R0..R3 to R4..R7 for the next division.
- The six digits receive glyph bias +1 and occupy `D840..D845`, least
  significant first. This is glyph encoding, not ASCII.
- Formatting reads `D83C`: bit 1 and mask 70h participate in leading-digit /
  width handling; bit 0 selects the final rendering branch.
- The reordered string starts at `D848`, terminated with FF. `1:D195` and its
  caller at `1:ECC3` publish generic XDATA pointer `01 D8 48` at `DCC6..DCC8`.
- The final branches enter `1:D2D8` or call `1:DC4F`, providing concrete
  downstream rendering candidates. Their full hardware-write chains are not
  yet reconstructed.

These combined correspondences are much stronger than a lone constant 100.
ASUS also has additional state-dependent formatting code, so this is not a
claim of exact source identity or a byte-identical build of the public routine.

### CONFIRMED static transfers / STRONG EVIDENCE manual caller

The thunk map resolves `1670 -> G(1)=09D4 -> bank 1:EAEB`. A raw long-transfer
search finds exactly three LCALL 1670 sites and no LJMP 1670 sites:

| Physical bank:site | Evidence | Value feeding D838..D83B |
|---|---|---|
| `10:C41E` | Reached instruction boundary | `10:C507` calls thunk `1862 -> bank 8:5FEF`, then zero-extends R7 and stores it with common helper 20C4 |
| `10:E9F7` | Reached instruction boundary | Zero-extended 16-bit value from XDATA D82E..D82F; format 30h |
| `4:F058` | Coherent manually decoded sequence; not reached by current CFG | Zero-extended byte from XDATA DA86; format 00h |

The first caller supplies the value read at DA6B to `8:5FEF` via R7 and sets
R5=0; the returned R7 becomes the displayed number. DA6B is a selector/state
candidate, not yet a battery value. At the third site, a subsequent DA86==0
test triggers another path: do not rename DA86 to SOC without tracing writers.
No raw direct LCALL/LJMP to EAEB was found in the image.

### Reproduction and next target

```powershell
uv run --no-project tools/analyze_numeric_renderer.py '<path-to-V020.bin>' --out work/numeric-renderer.json
```

`docs/maps/numeric-renderer.json` records the candidate, checked helper sequences,
data locations and caller evidence. The script rechecks the image fingerprint,
thunk destination, exact small formatting signatures and CFG membership.

Next concrete work: analyze `8:5FEF` and the producers of D82E..D82F and DA86;
establish whether any caller is the battery-percentage display. Also find the
indirect caller that reaches `4:F058`. All of these are static tasks.

**HYPOTHESIS:** this renderer could participate in the SOC display. Its identity
as numeric formatting does not establish that any of these three inputs is SOC.
Neither the hardware battery source nor the conversion to 0..100 is identified.

## 2026-09-28: complete setting-query contract at 8:5FEF

**CONFIRMED:** `8:5FEF..659F` is fully reconstructed as a selector/mode query,
with R7 selector, R5 mode, and byte result in R7. It reads cached internal state;
it does not acquire ADC/I2C/PMIC data. All transitive writes are query/conversion
scratch at D833..D83D. Selectors 50h..52h read DA21..DA23 and call
`1B74 -> 6:C2D4`, computing `clamp(byte-28,0,100)` exactly.

The complete branch table, XDATA effects, callers, callees, unreachable branches,
renderer provenance and limitations are in [SETTING_QUERY.md](SETTING_QUERY.md)
and `docs/maps/setting-query-*`. 130,824 bounded offline checks pass against an
independently reconstructed contract; 860/862 main instructions are exercised,
the remaining two being statically impossible guard fallbacks.

**STRONG EVIDENCE:** modes 0/1/2/3 mean current/max/min/step; the conversion
matches public `UserCommonAdjustRealValueToPercent`. No source field is called SOC.

One D82E:D82F producer is now confirmed: `10:D5ED` queries the D824 selector in
mode 0, then D5F3..D5F7 writes the zero-extended result before E816/E9CA renders it.
The scratch addresses have many other uses; their global writer set is not a
single battery variable's update function. Continue with activation-specific
provenance and the DA86 timer path.
# 2026-09-29 live transport / host ABI continuation

See [LIVE_READ_BENCH.md](LIVE_READ_BENCH.md) for verified host addresses,
image fingerprints and live tests. Backend-6 enumeration invalidates its open
bridge handle; enumerate before InitialDev. Raw I2CReadEx and DDCCIRead now
return validated DDC GET responses. This establishes transport, not SOC/XDATA.
NativeRead is a stub. ReadRegEx uses selectors; Read32BitRegEx modifies
FDE5 and writes FDD0..FDD3. Neither is an established passive XDATA dump.

The WinIsp singleton `[1020BCFC]` resolver at `10003DE0` now has 119 verified
resolution/store pairs for 118 API slots. Vtable+0C -> `10003530` -> object+BC
proves the cdecl ReadRegEx wrapper; command 15h proves the four-argument
ReadRegsEx call at `1001F75A`, shared with ReadMcuRegs on command 19h.
See [WINISP_OBJECT_ABI.md](WINISP_OBJECT_ABI.md) and its derived slot map.

The 8051 CFG now follows the explicitly checked 36-entry jump table at
physical `4:EC36` (entries EC37 onward, R7 values 1..36). This extends the
partial graph to 2,595 resolved thunk-transfer sites and 147,130 instruction
starts, with no overlaps or reserved opcodes. It does not prove global
logical-to-physical bank identity. The DA86/countdown classification stands.

## Live power follow-up (2026-09-30)
The validated gauge path now supports a supervised brightness/ED campaign; see [POWER_INPUT_LIVE.md](POWER_INPUT_LIVE.md). This does not identify a PMIC current-limit register. USB descriptors and host transport hooks provide no direct VBUS/current measurement. Preserve that distinction from battery V*I.
The EC/2FD4/1 three-byte status ABI and active handle provenance were rechecked in the pinned RHub/bridge DLLs. The live attempt at 16:38 UTC could not open a device, so it provides no controller-status bytes.

17:30 UTC live follow-up: EC status request now executed on active handle, rc=0x1F, no payload, guards intact and DDC healthy. This does not establish a PD/controller mapping. See POWER_INPUT_LIVE.md.

## Corrected EBE1 priority: decoded return route is display-side

The verified V020 decoded direct-edge inventory has only 9:E759 calling EBE1,
and only 9:E7F2 calling E703. E759 belongs to E703: E75C copies R7 to R5,
E75E jumps to E77C, and E77C returns R5 through R7. E7F5 then passes that
result to 13:3DE6, the previously identified display/scaler sink.
`trace_charge_policy_callers.py --summary` now asserts these exact transfers and
writes `docs/maps/charge-policy-return-route.json` without proprietary bytes.
Do not continue looking for a new PMIC call along this already traced return.

This is not a proof that ED has no hardware consumer. In particular the proven
setting-query selectors 04/43 return the inverse of D9FF.bit7; downstream users
of that generic getter can hide the dependency from a direct bit-reference
search. Those consumers and packed-state copies remain unresolved. The direct
8:635E branch returns this query value; 9:A802 feeds the VCP reply helpers,
and 10:BEC8 writes selection scratch D830. These are not controller registers.
Next bounded analysis: classify callers of 8:5FEF/thunk 1862 with selectors
04/43, preserving the distinction between raw call candidates and reachable CFG
sites. Derive a hardware-facing read before any further device experiment.

## OSD atlas mission
See [OSD_ATLAS.md](OSD_ATLAS.md) for current coverage. New 1:E43B resource resolver: 512 offline cases verify generic pointer return R3:R2:R1 equals D893..D895 with writes limited to that scratch. Atlas also exports all 36 exact 4:EC1F event targets. Text candidates retain unknown glyphs; full OSD mapping remains incomplete.

OSD text follow-up: FF segment skipping and F8..FE classification are now checked offline (36 and 256 cases). See OSD_TEXT_FORMAT.md and maps/osd-text-format.json. Width/font dispatch branches and FF06 font-byte output are localized. Next: prove width/font table bounds and the menu language validator, then key/state transitions.


OSD font milestone: tools/map_osd_font.py verifies 256 common widths, 2,340 three-byte transfers and 256 loop guards. A full cell uses 27 bytes; 1:DBCA computes 27*glyph + 3*triplet and writes three consecutive bytes to FF06. See docs/OSD_TEXT_FORMAT.md and docs/maps/osd-font-output.json. Pixel packing and peripheral setup remain unresolved. Next: recover menu category/label construction and distinguish EEED/F7B2 resources from E43B/D7A1 text; then navigation and persistence.

## OSD cell and menu provenance milestone

See [OSD_CELL_RENDERER.md](OSD_CELL_RENDERER.md) and maps/osd-cell-renderer.json. Separate resolver 1:EEED (512 checks) feeds 1:F7B2 cell streams; FE advances row, FD repeats the preceding glyph. The complete drawing leaf 8:D83D -> 6:F851 -> 8:EE13 -> 13:6137 writes C0/glyph/color to 0092 and configures 0090/0091/0094 (768 checks, 120 stream fixtures). Category query selector 0C returns DA0A low nibble into D823, selecting nine handlers (256 source + 256 dispatch checks). DA03 low six bits feed D855/D865 text segment selection through B613's fall-through into B617 (1,536 checks). Legal language bounds, handler identities, input transitions and SRAM setup remain open. No resource bytes or hardware I/O are included.

OSD language validation milestone: tools/map_osd_text.py now checks 8:7911 for every packed DA03 byte (0..20 accepted, 21..63 -> zero, high bits preserved), selector 32 in 259 getter cases and 6:BA79 masked update tail in all 65,536 old/new byte pairs. The update tail alone does not clamp to 20. See docs/OSD_TEXT_FORMAT.md and docs/maps/osd-text-format.json. Next: full language adjustment/persistence, category handler labels/settings and input/navigation; do not repeat validator discovery.

OSD extension-font milestone: map_osd_font.py now verifies 37,632 width cases (21 indices x seven prefixes x 256 glyph bytes) and 3,096 additional triplet transfers. All 22 extension width/font bases in banks 11/5/2/0 and shared FA dispatch are mapped in docs/OSD_TEXT_FORMAT.md and docs/maps/osd-font-output.json. Five width-table paths use narrow doubling and alias codes separated by 80h; unmatched widths return 12 for indices 0E..13 or incoming R7 otherwise. Mechanical fallbacks do not establish valid tokens. Next: legal glyph/family bounds, font/cell pixel layout and SRAM setup; navigation and language persistence remain unresolved.

OSD event milestone: tools/map_osd_atlas.py verifies all 256 DA6C dispatch inputs at 9:B8B2, all 256 clear-tail inputs at 9:BAE1 and five timer leaf writers (timer 04/05/0C/1A/1C -> display codes 01/02/09/0C/0E). Caller integration is 6:FC3E -> 1472 -> 9:FB97, with call 9:FBA6 into B8B2. See docs/OSD_EVENTS.md. DA6C pending-display-event semantics are strong evidence; raw-key enum, conditional handlers and schedule remain open. Next precise input/control target: 6:FC39 and 9:9CD9, following actual producers before assigning button meanings.

OSD input milestone: initial 2:DF25 classifier reads FF09, FE0D and SFR96h to form D826:D827 (2,048 checks). FF09 inclusive ranges BB..C4/8B..9A/2B..34/4B..54 set 0010/0020/0008/0004; digital zero inputs set 0001/0080. RL6492 reference corroborates ADC_A0 and PORT55 register roles without proving ASUS button wiring. Current DC9E:DC9F, previous DCA0:DCA1, getter F20F, copy F264 and store FDBB were each checked over all 65,536 words. See docs/OSD_INPUT.md and docs/maps/osd-input.json. Next precise priority: DF25 stability from DF91 through E0A2, then E6B6/E20F consumers and physical button/repeat/menu mapping. Do not confuse DCB7&1F system/display-state dispatch with this input word.

OSD full sampling milestone: map_osd_input.py adds 12,304 DF25-through-E0A2 fixtures, including eight retry-cap cases. DCA2:DCA3 caches returned input; absolute ADC delta<2 accepts stability, otherwise saved-sample retries stop at ten. Classification uses saved D828. Direct bit24h suppresses changed nonzero masks except 0001; DA6E bits0/1 are cleared for nonzero raw masks. Tests execute real 5:FBC3 delay early return with CAh=0, so physical timing is not proved. See docs/OSD_INPUT.md. Next precise priority: E6B6/E20F navigation/repeat consumers, bit24h producer and delay timer provenance.

OSD hold milestone: E3A9 caller gate passes only input 0010 to F2C6 (65,536 word checks). F2C6 saves the word, counts 5000 requests or 2500 when 7:F2FC returns 3, resamples until release/count zero, and toggles D9FD.bit6 at zero. All 256 old-byte toggle cases, four full holds and one release-abort fixture pass; other bits are preserved. Tests stop before 15C2 -> 8:DDB3 post-toggle effects and use CAh=0, so save behavior and elapsed timing remain unproved. Key-lock semantics are strong evidence only. See docs/OSD_INPUT.md. Next: 8:DDB3 post-toggle effects, E6B6/E20F/DA6D transitions, repeat and button labels; retain clock/flag24h qualification.

OSD post-toggle handoff milestone: 8:DDB3 calls validator 786B and hands source 01:D9FD, length 0024 (36 bytes), to shared storage writer 01D0. DA87.bit3 clear chooses offset 000E; set chooses 0032+0024*((D9FE>>2)&3), i.e. slots 32/56/7A/9E. All 65,536 DA87/D9FE combinations pass parameter checks; 16 full validator fixtures preserve D9FD.bit6 and reach expected slots. Tests stop before 01D0, so storage medium/completion and physical offsets remain open. This reuses the battery-cache shared storage ABI, not a new guessed protocol. See docs/OSD_INPUT.md. Next precise storage target: 01D0 from 8:DE1A; next navigation targets E6B6/E20F and DA6D/repeat.

OSD storage milestone: tools/map_osd_storage.py verifies 1,656 page plans, 4,096 actual register-frame executions, five complete slot writers, sixteen validator-to-writer fixtures, three timeout paths and 256 mux selectors. Common 01D0 splits the D9FD..DA20 block on 16-byte boundaries, uses A0/address mode1/interface0B, calls 0707 hardware-I2C register output then 14CC -> 0:6C06 polling (at most 50 attempts/page), and returns carry. FE08 is restored to 1 on tested failures; source/remaining length advances before the transfer. EEPROM/write-protect roles remain strong evidence; physical completion/chip identity remain open. All effects occur in offline bytearrays with explicit synthetic peripheral status. See docs/OSD_STORAGE.md and docs/maps/osd-storage.json. Next precise OSD targets: 2:E6B6/E20F navigation, DA6D transitions and adjustment/save callers.

OSD command/repeat milestone: tools/map_osd_commands.py verifies all 65,536 DD54 initial word branches, 105 mode/setting translation fixtures, 139,344 F9FB producer cases, 256 release tails, 256 timer01 flag updates, 145 actual scheduler fixtures and sixteen cancellations. Current/previous input changes publish DA6D and set DA6E.bit4; unchanged inputs consult bits3/2 or request timer01 with argument500/20. Timer01 -> 4:ECA3 sets bit2; default DD54 clears bits2/3 and cancels timer01. Setting01 copies category nibble from DA0C/DA0D/DA0B for inputs4/8/32. Physical buttons and full cadence/lifecycle remain unproved. See docs/OSD_COMMANDS.md. Next precise target: 9:A23E..A26A DA6B/DA6D table calls through2133, alternate8:E49A..E4EB, and post-handler repeat flag resets.

OSD callback milestone: tools/map_osd_handlers.py verifies 376 normal table selections at9:A23E/8FAF and all65,536 alternate setting/command pairs at8:E49A/38C0. Alternate settings5E..A8 select columns0..3; carry-sensitive guards send4/5 toFED6 and reject>=6. 455 distinct explicit callback seeds extend the existing optional CFG traversal from158,425 to166,916 starts (+8,491), with zero overlaps/reserved opcodes and no new indirect sites. Full handler effects remain unproved. Row32 adjustment callbacks lead to9:C031; next9:C0E6 ->19D6/8:B9A9 ->1652/8:8B52. Shared callback prelude1934 ->10:FEB0 is verified in65,536 DA6B/DA83 cases: DBFD..DC00 becomes00/24/04/08; DA6B=0 setsDA83=07, otherwise preserved; R7 is not consumed. Field roles and physical bank identity remain qualified. See docs/OSD_HANDLERS.md and docs/maps/osd-handlers.json.

OSD language preview/apply milestone: tools/map_osd_language_update.py verifies 10,752 row56 preview cases, 65,536 staged-byte writer cases, 256 dirty flags, 4,096 entry comparisons, 512 normal-row32 callback gates, 65,536 generic-setter exclusions and 512 display-event fixtures. Row56 commands1/2 advance/decrease DA48:DA49 modulo21 without changing DA03; command0 selects 9:C63A, whose checked C6B0 tail applies DA49 low6 while preserving DA03 high2 and sets DA69.bit0. Next 167C -> 8:E7E4 produces DA6C=0B for any dirty flags, reaching existing 9:BA6E dispatch. Normal row32 command1/2 calls C031 only in navigation mode, and generic 8:8B52 selector32 is a no-op except scratch; the previous numeric-adjustment next-target assumption is resolved. Full preview/apply drawing and entry transition remain open. See docs/OSD_LANGUAGE_UPDATE.md.

OSD language-save integration: 672 fixtures execute the writer tail/event dispatcher through BA6E ->15C2/8:DDB3 validator ->01D0 actual page/FIFO/poll instructions with synthetic FF5D status. All21 languages, four DA03 high-bit values, both DA87.bit3 states and four profiles preserve applied DA03 at concatenated payload byte6. BA6E clears DA69.bit0 before saving; BAE1 clears DA6C. Three timeout fixtures retain changed DA03 in RAM but clear dirty/event flags; BA6E does not test returned carry and issues no retry within itself. All256 DA69 inputs verify clear-before-call order0/2/3/5/1 ->15C2/15EC/19BE/15F2/15E6, preserving bits4/6/7 in the handler; other leaves are explicitly modeled out. No real persistence is asserted. Next: row32-to56 transition, 10:CA2A refresh/apply drawing, remaining dirty leaves.

OSD language entry/layout: tools/map_osd_language_layout.py verifies512 F550 caller/DA03 seed cases, 65,536 D370 prologue combinations, 1,024 target56 guard cases, 512 D735 ->BE8C transition prefixes and168 refresh geometry cases. F569 passes R7=56 to19EE ->10:D370; D370 sets DA68.bit6 iff previous DA6B equals target and clears D825..D82D/direct bit03. Target56 from row32 reaches D64B drawing, same-row entry returns D686. D735/BE8C writes DA6B=56 and D82E..D832=01,previous-setting,00,00,00; subsequent drawing excluded. F578 seeds DA48:DA49=00:(DA03&3F). CA2A's row56 CD7E..CEC6 arithmetic prepares four BE16 fields D83C/D83E/D840/D842 in groups0..7/8..15/16..20, with first-field bases300/456/612, third-field endpoints455/611/780 and second/fourth72+36n/108+36n. Tail sets D844:D845=00:07 and bit05, calls F142 R7=6. Highlight role is strong evidence; final physical coordinates/full entry drawing remain unproved. See docs/OSD_LANGUAGE_LAYOUT.md. Next: 10:F142 ->13:38C5 consumers/scaling, D662/F249 and C436/EBCD language-list drawing.

OSD window transfer: an additional336 fixtures execute CD7E ->F142 ->1AC0/13:36BB ->38C5 ->64CA ->0F4A/6:C3B9 through the actual instruction path with only FFF3 bits3/4 synthetic-clear completion. F142 translates first/third by DBFD:DBFE, second/fourth by DBFF:DC00 modulo65536, passes R6:R7/R4:R5/R2:R3/D84C:D84D. Callee stores D846..D84D and packs low12 coordinate bits at bytes3..8 of 12-byte bufferD84E..D859. Window6 uses control0118, XDATA01:D84E/count12/port0092; actual burst registers009F=0/FFF4=92/FFF6=13fixture/FFF7:FFF8=D84E/FFF9:FFFA=000C. Tail updates rotation lowbit at01A1 then2139 clearsDC8B..DC91. Reference ScalerOsdDrawWindow aligns ABI/layout/address/reset, making X/Y naming strong evidence; actual burst copy/visibility/legal ranges are unproved. Synthetic DAD3 inputs avoid zero-divisor state without assigning its live value/units. Next: D662/F249, C436/EBCD list drawing/names and entry prerequisites.

OSD language-list integration: tools/map_osd_language_list.py verifies63 actual DC4F segment-selection fixtures and21 complete9:F550 ordinary-entry runs (19,147,309 instructions), no drawing callee skipped. D153..D1C1 iterates D82F0..20; D1BB ->1A4E/1:DC4F receives row5+2*(index%8), col26+13*(index//8), style3, contextD853:D854:D855=0E:00:index. FC8F/E43B resolves code1:6D77; exactly21 FF-delimited segments end before family09 at6E1B. Actual DC8A..DCA2 skips explicit D855, independently of stored DA03 in the checked selections. Every full fixture returnsDA6B56/DA48:DA49=00:stored-language, DA03 preserved, with116 window preparations/3213 port writes. FFF3 completion, RAM39=1, FFFF=13, DAD3=60000000 and DC09/DBFC40 are synthetic prerequisites; physical burst/display/timing untested. Partial names reuse existing atlas decoder, not guessed native-script identities. See docs/OSD_LANGUAGE_LIST.md. Next: full9:C63A apply drawing and9:FA18 exit, native/accents fragment decoding.

OSD language lifecycle: --lifecycle adds21 complete entry ->increment preview ->decrement back ->unchanged C63A(no drawing/dirty) ->decrement preview ->changed C63A full drawing ->FA18 full exit cycles. All21 selected values cover wrap0->20; apply leaves DA03=selected,DA69=1,DA6C0B,DA6B56; exit returnsDA6B32 retaining selected/dirty/event. Changed apply also sets DCC4:DCC5=02CC and clears directbit25 viaFD52. Pending-save dispatcher is not run; page/save integration remains independent. No drawing callee skipped, no hardware-I2C register writes; same synthetic completion/init assumptions. Additional131,072 FA18 gate fixtures verify target32 iffDA68.bit6clear, otherwise currentDA6B, before1676/10:DE50; tail167C/8:E7E4. Next: DCC4:DCC5 02CC consumers and high-flag/modal/re-entry variants; native glyph identification.

OSD notifications: tools/map_osd_notifications.py verifies65,536 FD52 marker cases,512 GET02 status cases,2048 GET52 active cases and168 valid GETCC cases using original A3A0 dispatcher/13:6699 builder/checksum, existing pre-transport boundary. GET02 targetA462 returnsmax2/currentDCC4 unchanged; GET52 targetA5B7 returnsmaxFF/currentDCC5 ifbit25clear then setsbit25, otherwise current0 without readingDCC5; both setDCC4=1. FD52 sets2/R7 and clearsbit25; composed CC marker/GET02/GET52/GET02/GET52 yields2/CC/1/0. GETCC targetA726 returnsmax31/code9:9426[DA03&3F], with21 checked mappings and high2 preservation; invalidindices not asserted legal. Source-correlated names02NewControlValue/52ActiveControl/CCOsdLanguage are strong evidence. Protocol0D/01/06 at indices14/15/16 correlate to Simplified/Traditional Chinese/Japanese via pinned reference, native bitmaps unverified. ED marker shares change-report path, not receive SET proof. GET52 acknowledges runtime state; no live query sent. See docs/OSD_NOTIFICATIONS.md. Next: language SETCC mapping/validation/redraw/save.

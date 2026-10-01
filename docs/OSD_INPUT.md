# OSD input acquisition: analog/GPIO classifier and runtime word

SHA-pinned V020, existing static bank model, bounded offline execution only.
This establishes an input subchain; **physical button names, physical debounce
timing and navigation are not mapped yet**. No device read, command or patch.

## Initial acquisition at 2:DF25

The prologue clears D826..D82B, reads FF09 into D828, samples FE0D and SFR
bit 96h, then builds a big-endian word at D826:D827. The exact rules are:

| Source condition | OR mask |
|---|---|
| FF09 in 187..196 inclusive (BB..C4 hex) | 0010 |
| FF09 in 139..154 inclusive (8B..9A hex) | 0020 |
| FF09 in 43..52 inclusive (2B..34 hex) | 0008 |
| FF09 in 75..84 inclusive (4B..54 hex) | 0004 |
| FE0D equals zero | 0001 |
| SFR bit 96h equals zero | 0080 |

The four analog ranges do not overlap. The digital masks can combine with an
analog mask; the result must not be treated as a simple one-button enum.
All other analog byte values contribute zero analog bits.

**2,048 checks** execute every ADC byte with four distinct FE0D values and
both SFR-bit levels, stopping at F27A's first D826 read before stability logic.
The output matches an independent range/mask model. Writes are confined to
D826..D82B; no peripheral write occurs at this tested boundary.

The pinned [RL6492 register reference](https://github.com/Kingdomwhisky/RTD-Scaler-TEST/blob/3d38340ec8518a8888fd5d8dbb181c2a7418e11c/Kernel/Scaler/RL6492_Series_Scaler/Code/RL6492_Series_Mcu.c#L268)
identifies FF09 as ADC channel A0's conversion result. It also names
[FE0D as PORT55_PIN_REG](https://github.com/Kingdomwhisky/RTD-Scaler-TEST/blob/3d38340ec8518a8888fd5d8dbb181c2a7418e11c/Kernel/Scaler/RL6492_Series_Scaler/Code/RL6492_Series_Mcu.c#L159).
These support ADC/GPIO interpretation; they do not establish ASUS PCB wiring
or which physical button produces a given mask. SFR bit 96h is recorded as an
exact firmware input without assigning a board signal name.

## Current and previous runtime codes

| Field/routine | Verified contract |
|---|---|
| DC9E:DC9F | Current big-endian input word |
| 2:F20F | Read current word into R6:R7; no XDATA writes |
| DCA0:DCA1, 2:F264 | Copy current word into previous-word storage |
| 2:FDBB..FDC2 | Write R6:R7 to DC9E:DC9F |

Each of the three byte contracts was checked over **all 65,536 words**. The
write test stops exactly at the call into E6B6. It does not execute the consumer
or claim every word is a physically possible input.

The coherent caller sequence is:

```text
2:FDB0 -> FD49 conditional gate
       -> F264 (save previous word)
       -> DF25 (acquisition, then stability logic)
       -> FDBB (store returned R6:R7 into current word)
       -> E6B6
       -> conditionally E20F

2:FE36 -> F264 -> DF25 -> FE3C (same word store) -> E6B6
```

This connects the hardware-facing acquisition routine to runtime input
storage and navigation candidates. The initial classification checks and the
full return/stability checks below are separate coverage layers.

## Full sampling return and stability contract

The extended interpreter checks execute **2:DF25 through E0A2** in **12,304
fixtures**, using an independent input-sequence model. **DCA2:DCA3** is the
big-endian cached result:

1. If the initial mask equals the cache, return it immediately. A nonzero
   result clears DA6E bits 0/1.
2. On a changed mask, compare a new FF09 byte with saved D828. Absolute
   difference below 2 accepts stability. Otherwise replace D828 with another
   FF09 read, increment direct RAM 26h, and repeat up to ten attempts.
3. Reclassify using **saved D828**, even when the just-compared ADC byte differs
   by one and the stability test succeeds. The checks cover range boundaries.
4. A changed nonzero mask clears DA6E bits 0/1. If direct bit **24h** is set,
   clear that bit and suppress every mask except **0001**. Cache and return the
   resulting word. The bit's system meaning remains unassigned.

The fixtures cover every initial ADC byte, stable/delta-one/delta-two/wrap
sequences, both digital levels, matching/different caches and both flag states.
Eight extra cases reach the ten-retry cap. Digital inputs remain fixed within
each fixture; D829..D82B remain zero following the actual prologue.

Each retry calls thunk **0DAC → 5:FBC3** with R6:R7=0001. That delay routine
returns immediately if bit CAh is clear. Otherwise it waits for direct bit
1Eh and decrements its argument. The tests explicitly clear CAh and execute
the routine's real early-return branch: no timer interrupt or elapsed duration
is fabricated. Thus mask/cache/retry behavior is verified under these fixtures,
while **physical debounce timing and clock/timer provenance remain open**.

## Hold path for code 0010

Inside `2:E346`, the gate at **E3A9..E3B4** calls **F2C6** only when the
saved input word D820:D821 is exactly **0010**. All 65,536 possible words
were checked after the routine's earlier gates; no other word reaches that
call boundary. This links the analog BB..C4 classification to a hold operation.

`2:F2C6` saves the supplied word in D822:D823, initializes BE16 D824:D825
to **5000**, or **2500** if getter 7:F2FC returns 3. Under its allowed state
conditions, each pass calls 0DAC with argument one, decrements the counter and
resamples DF25. A changed input exits without toggling. At counter zero,
**F34F..F374 toggles D9FD.bit6**, preserving its other seven bits, and reaches
the banked call **15C2 → 8:DDB3** at F375.

256 old-byte cases verify the exact toggle. Four full holds verify delay-call
counts 5000/5000/2500/2500 with bit6 initially clear/set. An immediate release
aborts after one pass with carry clear and no toggle. Full-hold fixtures set
DCC9 high nibble to 0/3, DCB7 low five bits to 3, DA6B=0, D9FE.bit5=0 and
DA0F.bit0=0; earlier caller gates and alternative state conditions remain open.

The post-toggle call is a tested boundary: its persistence or other side
effects are **not executed or established** here. CAh is clear in fixtures,
so delay counts do not prove elapsed milliseconds. The known getter selector
33 returns the inverse of this same D9FD.bit6. Its gating/hold behavior gives
**strong evidence for a key-lock function**, while the setting's exact UI name,
physical button name, repeat behavior and save contract still need proof.

## Distinct display/system-state inputs

The [DA6C event service](OSD_EVENTS.md) calls `9:9CD9` before B8B2. That
routine's bounded table at 9D04 consumes R7 returned by thunk 1532:
`7:FED0 -> 7:E873 -> DCB7 & 1F`. This is a separate source from the DC9E:DC9F
word. Do not assign its eight table cases to physical keys merely because it
runs next to the display-event dispatcher. Its producer semantics remain open.

## Reproduce and next precise work

```powershell
uv run --locked --offline python tools/map_osd_input.py <local-V020.bin> --out docs/maps/osd-input.json
```

[Derived checks](maps/osd-input.json) contain masks/addresses and counts,
without proprietary bytes. Next: **E6B6/E20F** input consumers, button names,
repeat behavior and DA6D/menu transitions; identify bit24h's producer, the
delay clock/timer and **8:DDB3** post-toggle effects. Physical timings remain
qualified until that proof.

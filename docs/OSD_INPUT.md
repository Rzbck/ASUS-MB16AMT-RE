# OSD input acquisition: analog/GPIO classifier and runtime word

SHA-pinned V020, existing static bank model, bounded offline execution only.
This establishes an input subchain; **physical button names and full debounce/
navigation are not mapped yet**. No device read, command or firmware patch.

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
storage and navigation candidates. The classification tests cover the initial
sample only; they do not substitute for the full DF25 return/stability contract.

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
without proprietary bytes. Next: **DF25 from DF91 through E0A2**, including
DCA2:DCA3 comparison, the bounded retry counter and delay call through 0DAC;
then **E6B6/E20F** input consumers, button names, repeat behavior and DA6D/menu
transitions. Physical timings must remain qualified until clock/timer proof.

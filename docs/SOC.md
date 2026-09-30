# Battery SOC investigation

**LIVE BREAKTHROUGH 2026-09-30:** ASUS GET FE/EF/F0 reaches internal AA:10 through 12:E431 -> 1508 -> 0:6D00. Three live replies: 6E 84 56 1A 56 1A BA, source words 6742/6742, exact raw target **100%**. Use `tools/Run-SocReadBench.ps1 -Run -BatteryProxy`. See [BATTERY_LIVE_PROXY.md](BATTERY_LIVE_PROXY.md). DA4C itself remains unread; raw target and filtered display can differ during transitions. Earlier no-live-source statements below are historical. Next: establish runtime DA4C exposure through the FE GET handler or another proven read route.

## Current result — 2026-09-30

The actual OSD battery field is **DA4C**, populated from internal GPIO I2C AA:10, an integer piecewise conversion and a smoothing filter. The exact chain and reproducible offline checks are in [BATTERY_PERCENTAGE.md](BATTERY_PERCENTAGE.md). No live percentage has yet been read: the precise source read through the external USB bridge returned 2B0A. The user-reported 100% is only an observation. Earlier rejected paths below remain closed.

## Goal

Recover the exact 0..100 battery percentage displayed by the ASUS MB16AMT OSD and identify its source/provenance.

## Rejected static path: `1:F7B2`

`1:F7B2` looked SOC-like because it stores caller `R7` into `D833`, compares that value against decimal 100, selects an OSD resource, and continues through generic OSD formatting.

The banked ABI resolves thunk `0x1AC6 -> logical 1:F7B2`. The only decoded call edge to this thunk is:

- `10:B07D LCALL 1AC6 -> 1:F7B2`

Immediately upstream:

```text
10:B073  LCALL BE4A
10:B076  INC A
10:B077  MOVX @DPTR,A
10:B07A  MOV R5,#02h
10:B07C  MOV R7,A
10:B07D  LCALL 1AC6 ; -> 1:F7B2
```

`10:BE4A` is exactly:

```text
10:BE4A  CLR A
10:BE4B  MOV DPTR,#D836h
10:BE4E  MOVX @DPTR,A
10:BE4F  INC DPTR
10:BE50  RET
```

Therefore `BE4A` always returns `A=0`; `INC A` makes the value `1`; `R7=1` is what reaches `1:F7B2` on the proven caller path. This path is **not the dynamic battery SOC source**.

`D833` is also generic OSD state (many unrelated readers/writers) and must not be labeled SOC.

## Runtime `ReadMcuReg` capability probe

A narrow read-only probe compared `0x0033..0x0036` with `0xD833..0xD836` using the historical project P/Invoke guess:

```text
int ReadMcuReg(uint address, out byte value)
```

Every call returned the same non-zero result `0x00002B08` and left the output byte at zero. By itself that result was not enough to establish the ABI or validity of the returned status/value.

Offline PE/x86 inspection of the exported `ReadMcuReg` function at RVA `0x3CB0` then showed that one active communication branch loads the first stack argument and executes:

```asm
MOV EAX,[EBP+08]
OR  EAX,0000FF00h
```

before passing the address to the lower transport function. Thus `0x0033` and `0xD833` both become `0xFF33` on that branch. This is direct evidence that `ReadMcuReg` targets the low-byte MCU-register/SFR-style address space on this backend and is **not a valid primitive for reading XDATA `D8xx`**.

Do not perform a D8xx runtime sweep with `ReadMcuReg`/`ReadMcuRegs`.

## Current direction

Stop broad static searches for arbitrary `100` comparisons or generic numeric renderers. Identify a different exported read primitive that preserves a real 16/32-bit register address.

Current candidates for offline ABI inspection are:

- `ReadReg`
- `ReadRegEx`
- `ReadRegsEx`
- `Read32BitRegEx`
- `Read32BitRegsEx`

Only after a candidate's parameter count, output pointer convention and address width are established should a tiny read-only runtime validation be attempted. If a valid XDATA/register read primitive is established, correlate a narrow RAM region with the OSD battery percentage and then trace the matching variable statically.

No firmware writes, erase operations, ISP programming, or modified-image flashing are part of this step.

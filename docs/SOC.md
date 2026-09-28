# Battery SOC investigation

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

## Current direction

Stop broad static searches for arbitrary `100` comparisons or generic numeric renderers. Use a narrow read-only runtime capability test first:

- compare `ReadMcuReg(0x33..0x36)` with `ReadMcuReg(0xD833..0xD836)`;
- if high addresses alias the low byte, reject `ReadMcuReg` as a 16-bit XDATA reader;
- if high addresses are distinct, use a narrow runtime correlation monitor to locate a byte that follows the OSD battery percentage, then trace that variable statically.

No firmware writes, erase operations, ISP programming, or modified-image flashing are part of this step.

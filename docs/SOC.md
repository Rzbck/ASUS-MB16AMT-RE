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

## Runtime `ReadMcuReg` capability probe

A narrow read-only probe compared `0x0033..0x0036` with `0xD833..0xD836` using the historical project P/Invoke guess:

```text
int ReadMcuReg(uint address, out byte value)
```

Every call returned the same non-zero result `0x00002B08` and left the output byte at zero.

This does **not** prove that the high addresses alias their low-byte counterparts. The stronger interpretation is that the current native ABI/signature or required protocol state has not been established, so the returned values are not yet trustworthy.

Do not perform a D8xx runtime sweep with this signature.

## Current direction

Stop broad static searches for arbitrary `100` comparisons or generic numeric renderers. Before any further runtime memory reads:

1. inspect the native `WinComm.dll` export for `ReadMcuReg` offline;
2. determine export decoration, function RVA, RET convention and stack-argument clues;
3. only after the native ABI is understood, make a very small read-only validation call;
4. if a valid XDATA read primitive is established, correlate a narrow RAM region with the OSD battery percentage and then trace the matching variable statically.

No firmware writes, erase operations, ISP programming, or modified-image flashing are part of this step.

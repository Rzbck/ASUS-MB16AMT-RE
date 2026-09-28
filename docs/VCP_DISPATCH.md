# Exact Set-VCP dispatch (ASUS MB16AMT V020)

Status: **CONFIRMED static dispatch**, with experimentally corroborated ED semantics.

## Provenance

The DDC/CI RX structure is identified statically as:

- `D992 = RxBuf[2] = DDC command`
- `D993 = RxBuf[3] = VCP/source opcode`
- `D995 = RxBuf[5] = Set-VCP low value byte` for the simple 0/1 controls used here

At bank 9, `D992 == 0x03` (Set VCP Feature) branches to `9:9452`. The handler reads `D993` directly into `R7`, moves it to `A`, then calls the common inline byte-switch helper at `0:210D`.

The inline switch table at `9:946B` contains 38 entries and a default target. Because its selector is proven to come directly from `D993`, these entries are exact VCP opcode dispatches, not heuristic literal matches.

## Relevant exact entries

- `VCP D6 -> 9:9980`
- `VCP DC -> 9:9A11`
- `VCP E0 -> 9:9ABE`
- `VCP E3 -> 9:9B05`
- `VCP E4 -> 9:9B25`
- `VCP E9 -> 9:9C31`
- `VCP EB -> 9:9C5C`
- **`VCP ED -> 9:9C7A`**
- `VCP F0 -> 9:9B56`
- `VCP F1 -> 9:9BFC`

Default target: `9:9C9F`.

## Exact VCP ED handler

`9:9C7A` reads `D995` and updates `D9FF`:

```asm
9:9C7A  MOV DPTR,#D995h
9:9C7D  MOVX A,@DPTR
9:9C7E  MOV DPTR,#D9FFh
9:9C81  JNZ 9C8B
9:9C83  MOVX A,@DPTR
9:9C84  ANL A,#7Fh
9:9C86  ORL A,#80h
9:9C88  MOVX @DPTR,A
9:9C89  SJMP 9C8F
9:9C8B  MOVX A,@DPTR
9:9C8C  ANL A,#7Fh
9:9C8E  MOVX @DPTR,A
9:9C8F  MOV DPTR,#D9FFh
9:9C92  MOVX A,@DPTR
9:9C93  ANL A,#EFh
9:9C95  MOVX @DPTR,A
9:9C96  MOV DPTR,#DA69h
```

Therefore:

- `ED = 0` sets `D9FF.bit7 = 1`.
- `ED != 0` clears `D9FF.bit7 = 0`.
- both paths clear `D9FF.bit4`.
- the path then continues through `DA69` state handling.

## Experimental corroboration

Controlled live VCP tests already established:

- `ED = 0` => **Charging From NB/PC**
- `ED = 1` => **No Charging From NB/PC**

Combining that experiment with the exact Set-VCP dispatch gives **strong evidence** that `D9FF.bit7` is the internal policy flag meaning approximately **charging from notebook/PC is allowed** (active-high).

This does **not** yet identify the battery SOC acquisition path. The next static task is to follow all consumers of `D9FF.bit7` and the `DA69` continuation into the power/USB-C logic.

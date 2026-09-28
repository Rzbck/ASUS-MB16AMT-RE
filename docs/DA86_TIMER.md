# DA86 timer / OSD countdown path

Status: **CONFIRMED static behavior for the SHA-pinned V020 instruction stream**, with public Realtek timer code providing strong semantic corroboration. No device command or firmware modification was used.

## Summary

`DA86` is not a credible battery-SOC variable. It is used as a countdown value driven by user timer event `0x17`, rendered once per event invocation, decremented by one, and followed by completion/cleanup logic when it reaches zero.

This also removes the third known caller of the numeric renderer `1:EAEB` from the battery candidate set.

## Event dispatch into `4:EFDB`

The routine at `4:EC1F` dispatches on `R7` through a 36-entry computed jump table beginning at `EC37`.

The entry for event value `R7 = 0x17` resolves to `4:EFDB`:

```text
4:EC1F  MOV A,R7
4:EC20  DEC A
...
4:EC36  JMP @A+DPTR
...
4:EC79  LJMP EFDB
```

The table index is `R7 - 1`; `EC79` is entry 22, therefore the selected event ID is `0x17`.

The existing generic CFG did not recover this computed dispatch automatically. The path is nevertheless instruction-coherent and the table arithmetic is deterministic.

## One-second reactivation

At `4:EFDB`:

```text
4:EFDB  MOV R5,#17h
4:EFDD  MOV R7,#E8h
4:EFDF  MOV R6,#03h
4:EFE1  LCALL 0B72 ; -> 5:E671
```

`R6:R7 = 0x03E8 = 1000` decimal and `R5 = 0x17`.

The target `5:E671` scans the firmware timer-event table, searches for an existing event ID and installs/updates an event/time pair. Its structure strongly matches the public Realtek `ScalerTimerActiveTimerEvent(WORD usTime, EnumScalerTimerEventID enumEventID)`, whose time argument is in milliseconds.

Reference source:

- `Kernel/Scaler/ScalerCommonFunction/Code/ScalerCommonTimerFunction.c`
- `ScalerTimerActiveTimerEvent(...)`

Therefore the best-supported interpretation is: **reactivate/schedule user event `0x17` after 1000 ms**.

## DA86 decrement and display

Immediately afterward:

```text
4:EFE4  MOV DPTR,#DA87h
4:EFE7  MOVX A,@DPTR
4:EFE8  ORL A,#01h
4:EFEA  MOVX @DPTR,A
4:EFEB  MOV DPTR,#DA86h
4:EFEE  MOVX A,@DPTR
4:EFEF  DEC A
4:EFF0  MOVX @DPTR,A
```

So each invocation:

1. sets `DA87.bit0`;
2. decrements `DA86` by exactly one.

Later the same path copies `DA86` into the 32-bit input buffer used by the already identified numeric renderer:

```text
4:F044  MOV DPTR,#DA86h
4:F047  MOVX A,@DPTR
4:F048  MOV R7,A
4:F049  CLR A
4:F04A  MOV R4,A
4:F04B  MOV R5,A
4:F04C  MOV R6,A
4:F04D  MOV DPTR,#D838h
4:F050  LCALL 20C4
4:F053  CLR A
4:F054  MOV DPTR,#D83Ch
4:F057  MOVX @DPTR,A
4:F058  LCALL 1670 ; -> 1:EAEB numeric renderer
```

Thus the value displayed by the `4:F058` renderer call is the current byte value of `DA86`, zero-extended to 32 bits.

## Zero completion path

After rendering:

```text
4:F05B  MOV DPTR,#DA86h
4:F05E  MOVX A,@DPTR
4:F05F  JZ F064
4:F061  LJMP F129
```

Non-zero values return through the ordinary path. When the countdown reaches zero:

```text
4:F064  INC DPTR        ; DA87
4:F065  MOVX A,@DPTR
4:F066  ANL A,#FEh
4:F068  MOVX @DPTR,A    ; clear DA87.bit0
4:F069  MOV R7,#17h
4:F06B  LCALL 0B84     ; -> 5:F920
```

`5:F920` scans 16 timer slots, compares each valid event against `R7`, and clears the matching entry. This strongly matches public `ScalerTimerCancelTimerEvent(EnumScalerTimerEventID enumEventID)`.

The path then performs setting-dependent completion actions using `DA6B`; selectors `0x50..0x52` take a dedicated branch through `10:DE50` and `8:E7E4`.

## DA86 reference inventory

The verified image contains only three direct `MOV DPTR,#DA86` sites, all in this same coherent routine:

- `4:EFEB` — read, decrement, write;
- `4:F044` — read for numeric rendering;
- `4:F05B` — read for zero/completion test.

No immediate register-pair pointer literal `DA:86` was found in the targeted scan. The initial writer of the countdown value is therefore likely indirect (for example through a neighboring structure/helper) and remains unidentified. Finding that initializer is lower priority because the runtime role of `DA86` is already constrained by the timer/decrement/render/cancel chain.

## Consequence for the SOC search

The three known raw callers of numeric renderer thunk `1670 -> 1:EAEB` are now explained without requiring battery SOC:

1. `10:C41E` — generic current-setting display via `8:5FEF`;
2. `10:E9F7` — generic setting/min/max/current UI scratch path via `D82E:D82F`;
3. `4:F058` — the `DA86` one-second countdown described here.

Therefore **`1:EAEB` remains a numeric OSD renderer, but current evidence no longer supports it as the battery-percentage renderer**.

The SOC search should pivot to:

1. another numeric/digit rendering path used by the battery OSD;
2. the confirmed VCP `ED` handler and its charging/power-management call graph;
3. cached battery/power state written by the hardware-acquisition side rather than generic OSD setting queries.

## Safety

This conclusion comes entirely from offline analysis of the verified V020 image and public reference-source correlation. No monitor command, ISP action, reset, flash write or firmware mutation was performed.

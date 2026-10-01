# VCP `0xED` static candidate audit

Status: **the `9:F1C0 MOV R7,#ED` site is rejected as direct receive-side SET-handler evidence. It packages a change-report record.** The later [OSD notification audit](OSD_NOTIFICATIONS.md) executes its GET02/52 consumers and establishes exact status/acknowledgement behavior. Earlier consumer uncertainty below is historical.

The runtime experiment remains authoritative that VCP `ED` controls USB charging policy on this MB16AMT:

- `ED=0` -> Charging From NB/PC
- `ED=1` -> No Charging From NB/PC

This document concerns only the static firmware site `9:F1C0` that happens to load immediate `0xED`.

## Reconstructed path

The focused V020 trace confirms:

```text
9:F1C0  MOV R7,#EDh
9:F1C2  LCALL 9:FD52
9:F1C5  LCALL 9:A940
9:F1C8  LCALL thunk 167C -> 8:E7E4
```

`9:FD52` stores a two-byte record:

```text
DCC4 = 0x02
DCC5 = 0xED
CLR 25h
```

`9:A940` then sets `DA69.bit0 = 1`.

`8:E7E4` immediately reads `DA69`; because bit0 was just set, this path branches directly to `E824` and writes:

```text
DA6C = 0x0B
```

Therefore the exact local chain is:

```text
internal state change around D9FF.bit4
  -> R7 = ED
  -> DCC4:DCC5 = 02:ED
  -> clear internal bit 25h
  -> DA69.bit0 = 1
  -> DA6C = 0B
```

## DCC4:DCC5 provenance

A dedicated instruction-boundary-aware XDATA audit found only one direct read of each field.

Writers include:

- `9:FD52`: `DCC4=02`, `DCC5=R7`, then `CLR 25h`;
- `9:9460`: writes a value from `D993` into `DCC5`, then `CLR 25h`;
- `9:94EC`: writes two adjacent values into `DCC4:DCC5`.

The principal consumer around `9:A5B7` behaves like a pending-record handler:

```text
JNB 25h,A5C6
...
A5C6: read DCC5
       call processing helpers
       SETB 25h
A5D4: DPTR = DCC4
       jump into the common continuation
```

There is also a direct `DCC4` read at `9:A462` that jumps into the same larger dispatch region.

The later [verified consumer audit](OSD_NOTIFICATIONS.md) proves GET02 returns DCC4, GET52 returns DCC5 once when bit25 is clear, then sets bit25 and DCC4=1. DCC4 status/DCC5 changed-control-ID naming strongly matches the pinned DDC definitions.

## Consequence

The literal `0xED` at `9:F1C0` is a **reported changed-control identifier**, not evidence that this code is the receive-side MCCS VCP `ED` handler.

The earlier immediate-constant scan found six other decoded `0xED` uses as `ADD A,#ED`. Since `ADD A,#ED` is equivalent to subtracting `0x13` modulo 256, these are plausible compiler-generated switch-index normalization sites and are now the better static targets for locating a real `SetVCPFeature`-style dispatcher.

## Current next step

The immediate-constant search recommendation below is historical. The current
OSD continuation is the language SETCC mapping/save/redraw comparison documented
in [OSD_NOTIFICATIONS.md](OSD_NOTIFICATIONS.md); do not repeat the closed literal
heuristic merely because another OSD marker uses a VCP identifier.

Inspect the six `ADD A,#ED` regions as potential switch/table dispatchers, prioritizing regions that:

- access a stable DDC RX buffer / source-opcode byte;
- cluster many known advertised VCP codes;
- dispatch into setting/power handlers;
- have paired get/set or reply-building behavior;
- cross the runtime-proven charging-policy state path.

Do not rename any XDATA field as charge/SOC state without provenance.

## Safety

All conclusions above come from SHA-pinned V020 offline analysis. No device I/O, ISP action, reset, flash write or firmware mutation was performed.

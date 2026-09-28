# VCP `0xED` static candidate audit

Status: **candidate rejected as direct DDC/VCP-handler evidence; internal event/message interpretation is currently stronger.**

The runtime experiment remains authoritative that VCP `ED` controls USB charging policy on this MB16AMT:

- `ED=0` -> Charging From NB/PC
- `ED=1` -> No Charging From NB/PC

This document concerns only the static firmware site `9:F1C0` that happens to load immediate `0xED`.

## Candidate path

The focused V020 trace confirms:

```text
9:F1C0  MOV R7,#EDh
9:F1C2  LCALL 9:FD52
9:F1C5  LCALL 9:A940
9:F1C8  LCALL thunk 167C -> 8:E7E4
```

`9:FD52` stores a two-byte pair:

```text
DCC4 = 0x02
DCC5 = 0xED
```

and clears internal bit `25h`.

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
  -> DA69.bit0 = 1
  -> DA6C = 0B
```

## Why this is not promoted to the VCP `ED` handler

The surrounding code is setting/OSD-state logic rather than an obvious DDC RX opcode switch. The value `0xED` is explicitly packaged into `DCC4:DCC5`, followed by generic dirty/update flags. This shape is currently more consistent with an internal event/message identifier than with the receive-side MCCS `SetVCPFeature` dispatcher.

The earlier immediate-constant scan also found six other decoded `0xED` uses as `ADD A,#ED`, which can simply implement index normalization (`A -= 0x13` modulo 256); these are not evidence of VCP semantics by themselves.

## Current next step

Trace all readers/writers of:

- `DCC4`
- `DCC5`
- `DA69`
- `DA6C`

The first priority is the sole direct reader of each `DCC4` and `DCC5`. If those fields feed an OSD/event queue, the `9:F1C0` false-positive interpretation becomes much stronger. If they feed DDC or power-management code, reassess.

Do not rename any of these fields as charge/SOC state without provenance.

## Safety

All conclusions above come from SHA-pinned V020 offline analysis. No device I/O, ISP action, reset, flash write or firmware mutation was performed.

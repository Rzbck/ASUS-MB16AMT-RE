# DDC/CI RX/TX buffer identity

Status: **strong static evidence**, SHA-pinned ASUS V020. No device I/O.

## TX buffer

Bank 12 at `12:EF5E` writes:

```text
D9C0 = 6E
D9C1 = 88
D9C2 = 02
D9C3 = 00
```

This exactly matches the public Realtek `Get VCP Feature Reply` header layout:

```text
TxBuf[_DDCCI_SOURCE]      = _DDCCI_DEST_ADDRESS = 0x6E
TxBuf[_DDCCI_LENGTH]      = 0x88
TxBuf[_DDCCI_COMMAND]     = _DDCCI_CMD_GET_VCP_FEATURE_REPLY = 0x02
TxBuf[_DDCCI_RESULT_CODE] = 0x00
```

Therefore `D9C0` is **strongly identified as the DDC/CI TX-buffer base**.

At `12:EFB1`, ASUS V020 copies `D993 -> D9C4`. Public Realtek code performs the equivalent operation:

```text
TxBuf[_DDCCI_SINK_OPCODE] = RxBuf[_DDCCI_SOURCE_OPCODE]
```

This gives strong evidence that `D993` is the RX source/VCP opcode byte.

## RX buffer

Public Realtek indices are:

```text
_DDCCI_SOURCE        = 0
_DDCCI_LENGTH        = 1
_DDCCI_COMMAND       = 2
_DDCCI_SOURCE_OPCODE = 3
```

The ASUS layout is consistent with an RX base at `D990`:

```text
D992 = RxBuf[2] = command
D993 = RxBuf[3] = source/VCP opcode
```

At `12:E440`, ASUS reads `D992` and tests it against `0x03`. Public Realtek defines:

```text
_DDCCI_CMD_SET_VCP_FEATURE = 0x03
```

So `D992 == 0x03` is strong evidence for the Set-VCP command path.

## Important negative result: `12:EFF8`

The nearby `12:EFF8 ADD A,#EDh` is **not** a VCP-ED comparison. Its control flow dispatches R5 values `0x12`, `0x13`, and `0x14`; `0xED` is merely arithmetic `-0x13` modulo 256.

Do not use literal `0xED` occurrence scanning as the primary method anymore.

## Current target

Trace all direct and derived reads of `D993` reachable after `D992 == 0x03`, then identify the path for `D993 == 0xED`.

Desired chain:

```text
RxBuf[2] == 03 (Set VCP)
  -> RxBuf[3] == ED
  -> ASUS handler
  -> internal charge-policy state
  -> power/USB-C/battery logic
```

## Classification

- `D9C0` as DDC TX-buffer base: **STRONG EVIDENCE**, near-exact structural correspondence.
- `D990` as DDC RX-buffer base: **STRONG EVIDENCE**.
- `D992` as `_DDCCI_COMMAND`: **STRONG EVIDENCE**.
- `D993` as `_DDCCI_SOURCE_OPCODE`: **STRONG EVIDENCE**.
- `12:EFF8` as VCP ED dispatcher: **REJECTED**.

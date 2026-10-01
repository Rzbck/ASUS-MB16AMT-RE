# OSD parameter save: page planning and hardware-I2C register path

This extends the [post-toggle handoff](OSD_INPUT.md) from `8:DE1A` into
common writer `01D0`. Every check executes offline in the existing bounded
8051 interpreter. **No storage or monitor command was sent.** Register effects
below are firmware behavior in memory, not observed hardware completion.

## Confirmed ABI and page preparation

`01D0` accepts source generic pointer R3:R2:R1, length R4:R5 and logical
destination R6:R7. It initializes address mode 1, interface selector 0B,
base bus byte A0 and page size 10h. `0226` holds the destination as BE32
D830..D833, remaining length as BE32 D835..D838 and source pointer at
D839..D83B. Each chunk is `min(remaining,16-(offset&15))`; its bytes are
copied into XDATA D842 onward, then the source pointer and remaining length
advance **before** the transfer attempt.

The prepared slave byte is `(A0 + 2*((offset>>8)&FF)) & FF`. Mode 1 transmits
one low address byte. This is byte-level addressing behavior; it does not
establish legal capacity or permit treating the logical offset as a flash offset.

The 36-byte OSD block `D9FD..DA20`, including D9FD.bit6 and DA03, is split as:

| Selected logical offset | Page offset:length (decimal lengths) |
|---|---|
| 000E | 000E:2, 0010:16, 0020:16, 0030:2 |
| 0032 | 0032:14, 0040:16, 0050:6 |
| 0056 | 0056:10, 0060:16, 0070:10 |
| 007A | 007A:6, 0080:16, 0090:14 |
| 009E | 009E:2, 00A0:16, 00B0:16, 00C0:2 |

All these slots use bus byte A0. They come from DA87.bit3 and D9FE bits2..3,
as established in the handoff analysis, rather than guessed resource offsets.

## Confirmed hardware-I2C register frame

`04C3 -> 0707` receives slave R7, mode R5, address R2:R3, count D8A3,
payload pointer D8A4..D8A6=`01:D842`, and interface D8A7=0B.
`0707 -> 0FB0 -> 8:EAFE` selects that interface:
1019=80, 1032=00, 1033=00; 101A is left unchanged.

For this mode and count 1..16, the writer:

1. Masks FF57 with FC and FF58 with E7; waits for FF5D.bit5.
2. Writes FF5E in order: slave byte, low address byte, payload bytes.
3. Launches with FF55=`C0+2*count`, then waits for FF5D.bit0.
4. On success writes `old FF5D | 07` and returns carry set.

Each wait can execute 600 decrement passes; an unmet status causes carry
clear and toggles FF55.bit7 clear/set. The initial wait has 601 status reads
before exit, because the next pass checks the exhausted counter.

After a successful frame, `053A -> 14CC -> 0:6C06` sends the same slave
byte and zero address byte for this mode, waits on FF5D.bit0 with a 240-pass
counter, and returns carry. The caller allows **50 polling calls per page**,
resetting that counter after success. Do not describe these counts as milliseconds.

FE08 is written 0 before a frame and restored to 1 on page success or checked
failure. A zero-length entry returns carry clear without touching FE08.
Nonempty completion returns carry set; transfer/poll timeout returns clear.
`8:DE1D` returns immediately after the call, propagating carry without an
additional check. A transfer failure leaves the source/remaining count advanced
for the attempted chunk; the destination advances only after the frame succeeds.

## Corroboration and remaining interpretation

The pinned RL6492 primary reference identifies
[FF55..FF5E as I2CM control/status/transmit registers](https://github.com/Kingdomwhisky/RTD-Scaler-TEST/blob/3d38340ec8518a8888fd5d8dbb181c2a7418e11c/Kernel/Scaler/RL6492_Series_Scaler/Code/RL6492_Series_Mcu.c#L373),
and FE08 as PORT50. Its
[selector definitions](https://github.com/Kingdomwhisky/RTD-Scaler-TEST/blob/3d38340ec8518a8888fd5d8dbb181c2a7418e11c/Kernel/Common/Pcb_List.h#L535)
name 0B `_HW_IIC_PIN_40_41`; the
[RL6492 pinshare implementation](https://github.com/Kingdomwhisky/RTD-Scaler-TEST/blob/3d38340ec8518a8888fd5d8dbb181c2a7418e11c/Kernel/Scaler/RL6492_Series_Scaler/Code/RL6492_Series_Pinshare.c#L217)
selects EEIICSCL using the same 1019 register. This corroborates the hardware-I2C
route. ASUS PCB connectivity and the storage-chip identity remain unproved.

EEPROM page writing, ACK polling and FE08 write protection are **strong evidence**.
The exact chip, capacity, physical bus signals, real completion and power-loss
behavior remain open. The battery acquisition uses a separately reconstructed
GPIO-I2C path at `0:6D00` with bus byte AA; it must not be conflated with this
A0 storage route. The shared writer for the D9F7 cache was already known;
this adds page/frame/error behavior rather than rediscovering that ABI.

## Reproduce and coverage

```powershell
uv run --locked --offline python tools/map_osd_storage.py <local-V020.bin> --out docs/maps/osd-storage.json
```

The [derived report](maps/osd-storage.json) contains no firmware or payload bytes:

- 1,656 page-plan cases: all low offset bytes, selected higher banks/boundary
  carries, lengths 0/1/15/16/17/36. Only these checks model successful carry at
  the 0707/14CC call boundaries.
- 4,096 actual 0707 executions: all low address bytes and lengths 1..16,
  verifying FIFO order and control masks with synthetic FF5D=21h status.
- Five complete slot-writer fixtures and sixteen validator-to-writer fixtures,
  executing both 0707 and 6C06 with synthetic successful status. The latter
  verify that the validated D9FD..DA20 bytes reach the page payloads unchanged.
- Three timeout fixtures: initial ready, completion and all 50 poll attempts;
  256 interface selectors checked through actual EAFE execution.

Synthetic status supplies peripheral bits, not an I2C bus or storage emulator.
Alternative address modes/configurations are outside this verified contract.
Next OSD target: input consumers **2:E6B6 / E20F**, then DA6D transitions and
setting adjustment/save callers. The complete OSD atlas is still unfinished.

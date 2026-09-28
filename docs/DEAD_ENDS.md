# Dead ends and negative results

This file exists to prevent the next session from repeating hours of already-disproved tests.

## 1. VCP `E3` is not battery SOC

Observed allowed values:

```text
0, 25, 50, 75, 100
```

Longer tests showed E3 fixed at `100` while actual battery SOC was much lower, and at 99% battery E3 still read 100.

**Status:** closed.

## 2. Standard battery APIs do not expose MB16AMT

`Win32_Battery` and normal Battery PnP enumeration did not expose the monitor battery.

**Status:** closed unless a different ASUS/DisplayLink-specific driver API is discovered.

## 3. VCP `D6` is not a usable black-screen control

`D6=4` logically removes the monitor, Windows reconfigures topology, and the DDC handle vanishes so the monitor cannot simply be woken through the same path.

**Status:** do not use for topology-stable black-screen automation.

## 4. Blind `0x6E` subaddress map

Treating `I2CRead(0x6E, subaddress)` for `00..FF` as if it were a flat register map produced zeros / misleading behavior.

**Status:** invalid model; do not repeat.

## 5. Raw VCP sweep did not reveal SOC

A supported-VCP sweep across all `00..FF` was useful for inventory, but controlled `100% -> 99%` comparison found no SOC-valued supported VCP.

Only unrelated controls changed (`02`, `10`, `52`, `CA`).

**Status:** generic VCP search exhausted. Revisit only if firmware static analysis identifies a specific vendor code.

## 6. Generic fuel-gauge addresses through USB bridge

Read-only probes returned `0x2B0A` / no response at all tested registers for:

```text
TI bq27xxx / bq274xx : slave 0xAA
MAX1704x             : slave 0x6C
0x0B / Smart Battery : slave 0x16
```

**Status:** no externally reachable standard gauge found through this bridge.

## 7. RL6492 reference SY9329 PMIC at `0xE0`

Public RL6492 reference boards can use a Silergy SY9329 PMIC at `0xE0`, with state/BAT/VBUS/current registers.

On the actual MB16AMT, five repeated read-only samples of registers `04`, `06`, `07`, `08` all returned `0x2B0A`.

**Status:** not exposed through tested USB-I2C path; reference design is not ASUS-board proof.

## 8. `ReadMcuReg()` at current WinComm `DebugMode=2`

Controlled test at real OSD SOC `74% -> 73%`:

```text
T0: 256/256 addresses stable, all zero
T1: 256/256 addresses stable, all zero
changed registers: 0
```

The function returned success, but no live data.

**Status:** not a useful SOC/XDATA primitive in the current normal runtime state.

## 9. Signature handshake `77 11`

ASUS/Realtek-related probing repeatedly produced:

```text
write succeeds
read returns 6E 80 BE (DDC NULL)
```

Expected reference response `77 22 90` was never observed.

Both read-path interpretations tried during RE failed to obtain a service handshake.

**Status:** normal running monitor does not expose the expected signature handshake in the tested state. Do not loop it hundreds of times without new evidence.

## 10. Direct Realtek `77 55` debug switch

A targeted direct switch test produced:

```text
AVANT 6E: result=0, data=00
77 55 WRITE: 0
APRES 6E: result=0, data=6E
3A write to 0x6A: 0x2B09
0x6E still active
```

So the device did not switch from normal DDC `0x6E` to debug `0x6A`.

**Status:** do not send 0x6A register commands until a real mode transition is proven.

## 11. Passive touch-HID vendor listener

The EETI vendor HID collection was listened to passively for about a minute while OSD actions were performed. No useful input reports appeared.

**Status:** low-priority; probably unrelated to battery path.

## 12. Upstream Realtek hub PD helpers

`RHubLib` opened the Realtek hub, but PD status/VBUS helper calls returned `0x1F / ERROR_GEN_FAILURE` in the tested path.

**Status:** not a productive route for SOC; avoid spending time on generic hub APIs unless new board-specific evidence appears.

## 13. Random I2C scanning

Do not escalate to broad arbitrary I2C writes or blind scans. The battery path should now be derived from static firmware/source analysis first.

## What *isn't* a dead end

- static analysis of the actual ASUS V020 firmware;
- public RL6492 reference-source correlation;
- `WinIspPlugIn.dll` RE for a genuinely read-only dump/query primitive;
- tracing the OSD battery rendering path back to its data source;
- controlled VCP `ED` charge-policy automation (already proven).

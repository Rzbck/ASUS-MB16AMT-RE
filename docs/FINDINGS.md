# Consolidated findings

## Device identity

- ASUS ZenScreen Touch MB16AMT
- Realtek RL6492 scaler
- monitor ID: `AUS1661`
- panel/firmware marker: `AUO B156HAK02.0`
- firmware version marker: `V020`

Device-unique serial numbers are intentionally omitted from the public repository.

## Working user-facing controls

### Stable black screen without topology reflow

Avoid VCP `D6=4`: it logically removes the display and causes Windows topology changes/flicker.

Working approach:

1. locate the MB16AMT by model/monitor ID, not a mutable `DISPLAYx` number;
2. cover it with a borderless topmost black overlay;
3. set brightness VCP `0x10` to `0`;
4. restore the previous brightness afterward.

### USB charging policy

Controlled experiment proved VCP `0xED` maps directly to the OSD option:

```text
ED=0 -> Charging From NB/PC
ED=1 -> No Charging From NB/PC
```

Only ED changed when toggling the OSD option.

## Battery findings

- Battery SOC is visible in the OSD.
- Battery SOC is not visible through Windows `Win32_Battery` / standard battery PnP.
- A full supported-VCP comparison across a real `100% -> 99%` drop produced no SOC-valued VCP.
- `E3` is not SOC.
- common external fuel-gauge addresses tested through the ASUS USB-I2C bridge did not respond.
- RL6492 reference PMIC `0xE0` did not respond through the bridge.
- `ReadMcuReg()` returned zeros across `00..FF` at both 74% and 73%.

Conclusion: the OSD SOC is likely obtained through an internal board path that is not directly exposed by the tested Windows-facing transports.

### Numeric-renderer path status

The strong numeric renderer candidate at `1:EAEB` is still valid as a generic OSD number renderer, but all three known raw callers are now explainable without battery SOC:

- `10:C41E` displays a generic current setting through `8:5FEF`;
- `10:E9F7` displays generic setting UI scratch from `D82E:D82F`;
- `4:F058` displays `DA86`, now classified as a one-second countdown value.

`DA86` is decremented once per user timer event `0x17`, rendered numerically, and when it reaches zero the path clears `DA87.bit0` and cancels event `0x17`. See `docs/DA86_TIMER.md`.

Therefore the battery OSD probably uses a different digit/number rendering path. The SOC search should no longer assume `1:EAEB` is involved.

## DDC/CI observations

Capabilities string observed:

```text
(prot(monitor)type(LCD)model(ASUS MB16AMT)
 cmds(01 02 03 07 0C E3 F3)
 vcp(02 04 05 08 10 12 14(05 06 08 0B) 16 18 1A 52 60(11 13 14) 62
 86(02 0B) 87(00 0A 14 1E 28 32 3C 46 50 5A 64) 8A
 AA(01 02 03 04 FF) AC AE B2 B6 C6 C8
 CC(01 02 03 04 05 06 07 08 09 0A 0C 0D 11 12 14 1A 1E 1F 23 30 31)
 D6(01 04 05) DC(00 03 0B 0D 15 16 17 18) DF
 E0(01 02 03) E3(00 19 32 4B 64) E4(00 01) E9(00 01)
 EB(00 01) ED(00 01) F0(00 01 02 03 04) F1(00 01) FD FF)
 mswhql(1)asset_eep(40)...)
```

Notable runtime behavior:

- transient DDC glitches can return zero/mutated values; conclusions should rely on repeated stable reads or controlled A/B tests;
- `52` behaves like an activity/active-control indicator;
- `CA` changes with OSD/button state;
- `10` is brightness;
- `02` is a new-control/change indication;
- `ED` is the only confirmed battery/charging-related vendor VCP.

## ASUS updater / communication

- `WinComm.dll` x86
- communication plugin ID used by ASUS package: `6`
- native host must be placed in the updater root for `WinComm.dll` plugin discovery to find `Comm/*.dll`
- three communication modules load in the working setup
- one USB device is found
- known ASUS addresses after autodetect:
  - ISP: `0x94`
  - continuous ISP: `0x96`
  - debug: `0x6A`
- normal DDC/scaler operation observed at `0x6E`

## Firmware architecture

- extracted image: `0xE0000` bytes
- repeated 64 KiB bank structure
- code pattern is consistent with banked 8051-family Realtek firmware
- no useful plain ASCII battery/charge/SOC labels were found in the firmware image

## Public-source correlation

`Kingdomwhisky/RTD-Scaler-TEST` provides highly useful RL6492 reference source. It confirms the Realtek concepts around normal DDC/CI (`0x6E`), debug (`0x6A`), signature protocol, debug read/write commands, timer-event management, and PMIC interfaces.

Treat that repository as a structural reference, not as proof that ASUS used every reference component or compile-time option unchanged.

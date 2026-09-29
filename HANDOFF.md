# Handoff — ASUS MB16AMT / RL6492 RE

**Last updated:** 2026-09-29

**Live continuation:** administrator access now works. Backend 6 initializes.
Moving `GetDeviceCount` BEFORE `InitialDev` restores USB DDC GET reads; the
enumerator invalidates the lower open handle. Both raw I2CReadEx and DDCCIRead
returned three checksum-valid brightness samples matching Windows DDC. The
first response following EDID failure can lose its initial byte; it is rejected.
SOC and XDATA access remain unresolved. See `docs/LIVE_READ_BENCH.md` and
`tools/Run-SocReadBench.ps1`. The old ReadRegEx D8xx probe is retired because
its internal selector writes and address-space meaning were not validated.

Historical `2B08` failures are transport setup failures, not evidence that the
monitor lacks a register. Do not repeat independently closed VCP/gauge sweeps.

DDC-only control: six valid replies, including the first; the wrapper defaults
to this sequence. EDID tests are optional. The pinned WinIsp object resolver
and ReadRegEx/ReadRegsEx ABI are now verified by CFG dataflow; see
`docs/WINISP_OBJECT_ABI.md`. Run the existing campaign with uv; its deep pass
includes this proof. Physical bank 4's EC36 jump table is now modeled.

**Latest continuation:** `DA86` is now classified as a one-second OSD countdown,
not battery SOC. User timer event `0x17` dispatches to `4:EFDB`, schedules itself
again with `0x03E8 = 1000 ms`, decrements `DA86`, renders it through `4:F058 ->
1670 -> 1:EAEB`, and clears/cancels event `0x17` when the value reaches zero.
See `docs/DA86_TIMER.md`.

This closes the third known raw caller of numeric renderer `1:EAEB`: all three
known callers are now explained by generic settings/countdown UI rather than SOC.
Do **not** continue assuming `1:EAEB` is the battery renderer. The active static
priority is now an alternate battery digit/rendering path plus the confirmed VCP
`ED` handler / charging-power call graph.

`8:5FEF` is completely mapped as an internal setting query (R7 selector, R5
current/max/min/step mode, result R7), with 130,824 offline checks. See
`docs/SETTING_QUERY.md` and `docs/maps/setting-query-*`. No I2C/ADC/PMIC
acquisition occurs in its transitive closure. Selectors 50..52 convert
DA21..DA23 with clamp(byte-28,0,100). D82E:D82F is reused scratch; one
renderer-producing assignment is traced from this query at 10:D5ED. Do not
repeat the 8:5FEF branch audit.

This file is the canonical continuation point. Read it before running new probes.

## Latest milestone — banked-call ABI (2026-09-28)

Read the continuation section of `docs/STATIC_MAP.md` and `docs/maps/` before
using older bank-address notes. The immediate ABI priority is now substantially
resolved, entirely offline, against the verified V020 file:

- Correct selector entries: `2600 + 10h*N`, not `2603 + 10h*N`.
- Gates `09C2 + 12h*N` push old-bank selector and destination onto the stack.
- 741 common thunks at `0AE8..1C45` map to banked destinations in banks 0..13.
- Callee RET -> old-bank selector -> caller RET restores the previous bank.
- 27 non-table FFFF occurrences: 25 MOVX-read forms (24 CFG-reached; one
  context-supported), two generic-pointer -1 offsets, no direct write forms.
- Public `Kernel/Common/L51_bank.a51` SELECT/SWITCH macros corroborate the ABI.
- Offline checks pass 10,374 round trips and 2,744 nested bank triples.
- A partial, instruction-boundary-aware graph records 2,540 thunk transfer
  callsites; 54 indirect-jump contexts remain unresolved. This is not a complete
  function graph or proof that every static entry executes at runtime.

Reproduce with `uv run --no-project tools/analyze_banked_abi.py <firmware> --out work/abi`.
There are no Python third-party dependencies. The script verifies image size/SHA.
Do not infer boot recovery or live logical/physical mapping from offline tests.

**STRONG EVIDENCE numeric renderer:** bank `1:EAEB`, thunk `1670`, matching
six-digit extraction and formatting in public `OsdPropShowNumber`. Its three
known callers are now classified as non-battery UI paths; retain the renderer
identity but drop the SOC-specific assumption. See `docs/maps/numeric-renderer.json`
and `docs/DA86_TIMER.md`.

No new runtime probe is justified by the current static work alone.

## 1. Objective

Primary objective: obtain the **battery percentage / SOC** that the MB16AMT OSD displays, programmatically from Windows, then use it for automation (for example charge policy). Secondary objectives: understand ASUS firmware/update transport and preserve a topology-stable black-screen control.

## 2. Hardware / Windows identity

- Product: ASUS ZenScreen Touch **MB16AMT**
- MCCS / monitor model: `ASUS MB16AMT`
- monitor short ID: `AUS1661`
- device-unique serial numbers intentionally omitted from the public repository
- scaler: **Realtek RL6492**
- DisplayLink composite device:
  - `USB\VID_17E9&PID_437B&MI_01...` display
  - `USB\VID_17E9&PID_437B&MI_02...` USB audio/media
  - composite parent uses `VID_17E9&PID_437B`; device-specific suffix intentionally omitted
  - upstream Realtek hub `VID_0BDA&PID_5412`
- touch controller: `USB\VID_0EEF&PID_C000...` (EETI-style HID)

Do **not** hardcode the Windows `DISPLAYx` path; it changes after topology events.

## 3. Strongest confirmed result: charge policy is VCP ED

Controlled A/B test at 100% battery:

```text
A: Charging From NB/PC
B: No Charging From NB/PC

DIFF CHARGE ON -> OFF
ED: current 0 -> 1 | max 1 -> 1
Total changes: 1
```

Therefore on this unit:

```text
VCP ED = 0  => Charging From NB/PC
VCP ED = 1  => No Charging From NB/PC
```

This is the best confirmed vendor-specific control found so far.

Important behavior: with `No Charging From NB/PC`, the screen may still be powered directly by USB-C, so the battery can remain flat for a while instead of immediately discharging. It eventually did drop in the controlled test.

## 4. Battery SOC is NOT an ordinary VCP

Controlled battery test:

```text
100% -> 99%
```

Only these supported VCP values changed:

```text
02: 1 -> 2
10: 0 -> 100
52: 0 -> 96
CA: 1 -> 2
```

These changes are attributable to normal monitor/control activity (new-control flag, brightness, active-control/OSD behavior), not SOC.

Vendor VCP snapshot at 99% included:

```text
E0 max=3   current=1
E3 max=100 current=100
E4 max=1   current=0
E9 max=1   current=0
EB max=1   current=0
ED max=1   current=1
F0 max=4   current=0
F1 max=1   current=1
FD max=1   current=1
```

`E3` stayed `100` while battery was `99%`, and previous longer tests also showed E3 fixed at 100 while SOC was lower. **Do not revisit E3 as a battery candidate.**

## 5. DDC/VCP state

Observed VCP capability string contains:

```text
02 04 05 08 10 12 14 16 18 1A 52 60 62 86 87 8A AA AC AE B2 B6 C6 C8 CC D6 DC DF E0 E3 E4 E9 EB ED F0 F1 FD FF
```

Notable findings:

- `D6=4` really powers/logically removes the monitor; Windows topology reflows/flickers and DDC cannot wake it after the handle disappears.
- `E3` is a five-level control with values `0,25,50,75,100`, not SOC.
- `ED` is charge policy, proven above.
- Raw GET-VCP sweep over `00..FF` showed many unsupported responses, but no hidden SOC feature.

## 6. Topology-stable black screen

Working strategy:

1. target monitor by `ASUS MB16AMT` / `AUS1661` rather than `DISPLAYx`;
2. show a borderless topmost black WinForms overlay on that monitor;
3. set VCP brightness to `0`;
4. restore the previous brightness when leaving black mode.

This avoids Windows topology changes and was user-validated as working well.

## 7. Official ASUS firmware package

Package:

```text
ASUS_MB16AMT_FW.zip
SHA256 8c070d21a9ff95ab9916941fc77c41e913c727d92ac891dca2e26662e18e71dc
```

Outer ZIP:

```text
MB16AMT series FW update SOP_V1.0.pdf
OneKeyUpdate_MB16AMT_20211227.sfx.exe
```

SFX contains the updater payload and the actual scaler image:

```text
ASUS_RL6492_MB16AMT_Project_AUO_B156HAK02_FF000_20211227_V020_4D38_ELot5_reduce.bin
size    917504 / 0xE0000
SHA256  1e75681279bf974d2810e6d2ed91aabbeda35de3fabe1881733aa8a12319cb0c
```

Firmware ASCII marker:

```text
#01V020AUO B156HAK02.0URLMB16AMT
```

The image is banked and strongly resembles an 8051-family Realtek firmware layout; repeated bank vectors appear at 64 KiB boundaries.

## 8. ASUS updater stack — confirmed

Extracted components include:

```text
OnekeyUpdate.exe
WinComm.dll
WinOperateCScaler.dll
WinSignatureVerify.dll
PlugIn/WinIspPlugIn.dll
PlugIn/Option/WinIspSettingPlugIn.dll
Comm/Comm_UsbHubI2C.dll
Comm/Comm_GLHubI2C.dll
Comm/Comm_TypeCI2C.dll
Comm/Comm_RealtekUSB.dll
Comm/UsbHub/RHubLib.dll
Comm/UsbHub/RtHub_USB2I2C.dll
```

Important `IspSetting.ini` values:

```text
enumActionType=6
enumDigitalSignatureType=1
enumSWDigitalSignatureMode=4
enumBootCodeType=1
enumIspMode=1
ulTimeAfterCommand=200
ulCommandRetryCount=10
bAutoDetectSlave=1
ucSpecifiedSlave=148      ; decimal 148 = 0x94
bResetMcu=1
ulIspSpeed=200
enumCommID=6
```

Updater log from 2021 shows one successful ISP session:

```text
ScalerType: 0x2F
IDCode0: 0xCE
IDCode1: 0x23
Flash ID: C2 20 14 13
Flash Name: MX/KH25L800X
Banks 10 -> 0 erased/programmed successfully
```

Other historical attempts failed entering ISP with error `0xA`.

## 9. WinComm host behavior

Critical discovery: `WinComm.dll` discovers communication plugins relative to the **host EXE path**, not merely the current working directory. The x86 test host must therefore live in the extracted updater root.

Working initialization:

```text
Comm modules : 3
SetCommByID(6): 0x0
CommID: 6
Devices: 1
InitialDev: 0x0
AutoDetectSlaveAddr: 0x0
ISP slave:        0x94
continuous slave: 0x96
debug slave:      0x6A
DebugMode:        2
```

`AutoDetectSlaveAddr()` knows these triplets:

```text
94 96 6A
64 64 68
54 56 58
```

## 10. Dead paths already proven — DO NOT repeat blindly

### `ReadMcuReg()` / 0x94

A controlled `74% -> 73%` run read all 256 addresses five times at each SOC:

```text
T0 74%: 256/256 stable, 0 non-zero
T1 73%: 256/256 stable, 0 non-zero
Diff: 0 registers changed
```

So the current `ReadMcuReg` path returns success but zero data and is not the live SOC RAM path.

### Generic external fuel gauges

Direct bridge reads to common gauge addresses all returned `0x2B0A` / no response:

- TI bq27xxx / bq274xx at `0xAA`
- MAX1704x at `0x6C`
- Smart-Battery-ish `0x16`

### RL6492 reference PMIC at 0xE0

Public RL6492 reference source uses Silergy SY9329 at `0xE0`, with BAT/VBUS ADC registers, but direct MB16AMT bridge reads of `0xE0` registers `04/06/07/08` returned `0x2B0A` in 5/5 samples. Do not assume the ASUS board exposes that reference PMIC through the USB bridge.

### Signature handshake / debug switch

Observed ASUS/Realtek signature handshake attempt:

```text
write 6E/71 payload 77 11 -> result 0
read -> 6E 80 BE ... (DDC NULL)
```

No `77 22 90` handshake reply was obtained.

Direct `77 55` attempt also failed to switch to debug:

```text
before 6E: accessible
after  6E: still accessible
write to debug 6A/3A: 0x2B09
=> 0x6A did not become active
```

Normal `0x6E` remained active afterward, so no restore was needed.

### Generic 0x6E subaddress scan

Treating every `0x6E` subaddress `00..FF` as a register map was invalid. Repeated read-only scans produced zeros and are not a useful SOC primitive.

### Touch HID vendor collection

Passive listening on the EETI vendor HID collection produced no useful input while opening the OSD. This is likely touch-controller-specific and is not a priority battery path.

## 11. Public RL6492 source research

Useful reference repo discovered:

```text
Kingdomwhisky/RTD-Scaler-TEST
```

It contains Realtek RL6492 source/reference code, including:

- `Kernel/Scaler/RL6492_Series_Scaler/Code/RL6492_Series_Mcu.c`
- `Kernel/Scaler/ScalerCommonFunction/Code/ScalerCommonDebug.c`
- `Kernel/User Common Function/Code/UserCommonSignDdcciFunction.c`
- `Kernel/User Common Function/Header/UserCommonSignDdcciDefine.h`
- `User/Device/Code/TypeC_Pmic_SILERGY_SY9329.c`

Important: this is **reference Realtek code, not proof of ASUS's exact MB16AMT board configuration**.

Reference code defines:

```text
normal DDC/CI slave = 0x6E
debug slave        = 0x6A
signature subaddr  = 0x71
signature cmd type = 0x77
handshake req      = 0x11
handshake reply    = 0x22, pass=0x90
change-to-debug    = 0x55
```

It also defines debug read command `0xBB` and XDATA access semantics, but those commands are unusable until the monitor actually enters 0x6A debug mode.

## 12. Best next move

Do **not** keep adding random I2C addresses or VCP scans.

Highest-value next work is static firmware RE:

1. locate the alternate number/digit path actually used by the battery OSD; the three known `1:EAEB` callers are now classified as non-battery UI;
2. statically identify the handler for confirmed VCP `0xED` and follow it into charging/power-management state;
3. find cached battery/power fields adjacent to that path and trace their writers back to I2C/ADC/PMIC/gauge acquisition;
4. cross-reference those calls with RL6492 public reference functions/macros;
5. only then design one targeted read-only runtime probe.

Secondary path: inspect `WinIspPlugIn.dll` further for a **non-destructive read/dump primitive** that can expose XDATA/flash without entering destructive ISP. `DumpFlash` exists as an export, but do not call it blindly until its initialization/context requirements and mode transitions are fully understood.

## 13. Safety constraints for continuation

- Prefer static analysis + read-only probes.
- Do not call `ChipEraseFlash`, `IspFlash`, erase/write helpers, or arbitrary flash operations.
- Do not flash a modified image until signature/checksum/dual-bank/recovery behavior is understood.
- Do not assume `0x6A`, `0x94`, or a PMIC address is active just because it exists in reference code.
- Every runtime write should be justified by ASUS or Realtek code and have a known restore path.

## 14. What the next agent should ask the user to do

Ideally: nothing immediately. First spend time on static analysis and public-source correlation. Only ask the user for a new probe once it tests a specific hypothesis that the firmware/source analysis supports.

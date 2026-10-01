# Handoff — ASUS MB16AMT / RL6492 RE

## Current mission: complete OSD mapping

The user superseded the power-input investigation with complete static OSD mapping for future modification planning. Start at [docs/OSD_ATLAS.md](docs/OSD_ATLAS.md). Verified layers now include text pointers/segments, common font-byte output, the separate cell-stream renderer, menu category dispatch and menu-text language provenance. The complete map remains unfinished. No hardware mutation or flash is part of this task.

Latest OSD milestone: [docs/OSD_EVENTS.md](docs/OSD_EVENTS.md) verifies256 complete event09 paths and131,072 statuswriter fixtures. Event09 resetsDA6B=0,writesDCC9low3,retainsDA03/DA72/dirtyDA69/DCCA,andclearsDA6C. Withdirtybit0,nestedF439 publishes0B at8:E829 butouterBAE1 overwrites0 at9:BAE5; localoverwrite isconfirmed,notpermanentglobalsettingsloss. Event02 reachesclockwait2:FA66;waitexit fixture thenhitsunsupported82 at2:FDF8. Next precise target: **verify/addANL C,bit82 support,event02waitexit paths andRAM42:43 producer**, thennavigationentry/DA6E lifecycle. FullOSDmap remainsunfinished.

## Current hardware experiment gate

No USB power tester is available (user confirmed). The validated software paths
provide battery telemetry but no input VBUS/current or proven current-limit
register. Full-brightness improvement remains unachieved. See
[POWER_MEASUREMENT_GATE.md](docs/POWER_MEASUREMENT_GATE.md) for the evidence,
why battery watts cannot identify the bottleneck, and the minimal passive
external observation. Do not repeat closed reads or substitute speculative
writes. Offline query-consumer work remains unresolved; only new protocol
proof or new physical measurement can justify another input-power test.

## Latest live result (2026-09-30)

**Return-route correction:** the known 9:EBE1/EC06 return feeds E703 then the already identified display sink 13:3DE6. Verified edge summary is in docs/maps/charge-policy-return-route.json. Next unresolved ED dependency: callers of generic setting query 8:5FEF with selectors 04/43, not another pass over EBE1. No hardware controls changed in this analysis.

**17:30 UTC update (supersedes absence below):** USB returned; the targeted EC status read returned 0x1F without modifying the guarded buffer, with valid DDC before/after. Passive controls=100/ED0; three fresh battery samples=4177 mV, -784 mA, -3.275 W. No settings changed. Do not repeat EC. Next: resolve the non-display 9:EBE1/EC06 policy consumers to a proven power output/source classification; actual USB input power remains unmeasured.

**16:39 UTC follow-up:** current USB data path is absent (no monitor Realtek/DisplayLink/touch devices; backend count=0, InitialDev=0x2B04). The new guarded `-HubStatus` probe was not sent. Resume it once enumeration returns; no reset or power-cycle was attempted.

See [POWER_INPUT_LIVE.md](docs/POWER_INPUT_LIVE.md): completed supervised brightness/ED campaign, original 100/ED0 restored twice with readback. At ED0, 100% brightness discharges (~1.9–2.6 W observed); 25% and 0% charge positively. ED1 at 100% approaches -7.9 W. These are battery watts, not USB input watts. USB2 high-speed topology and 500 mA DisplayLink configuration descriptor are verified; actual VBUS, input current, PD contract and current limit remain unknown. Next distinct live read: validate active RHub handle/module and test the three-byte RsHub_SmbusGetTPCPDStatus IN request once. No current-limit write is justified yet. Keep injected tracing separate from state-changing campaigns.

**Current priority: live USB input power. Read HANDOFF_DIRECT_MACHINE.md first.** The battery source is validated; the timer and FE-dispatch notes below are retained evidence, not the current priority.

**97% confirmed live:** three source reads at 07:00:34Z returned 6190/6742 -> x=9181 -> target 97%, matching the user OSD report. Timer setup 5:E268 now matches the reference millisecond routine: nominal acquisition ~1 s and continued filter steps ~13 s (strong evidence, physical timing unmeasured). FE GET dispatch was checked in 65,544 offline cases; remaining cache-read investigation is inside service 12:F684 and diagnostic leaves, not selector guessing. See `docs/BATTERY_LIVE_PROXY.md`.

**100% -> 99% live validation:** on 2026-09-30, the user reported OSD 99%; three fresh source samples were 6360/6742, 6359/6742, 6359/6742. The exact firmware curve independently returns **99%** for all three (raw ratios 9433/9431 basis points). Brightness was 100, so it is not the source of this result. See [evidence](docs/BATTERY_LIVE_PROXY.md). Direct DA4C access and transient filter timing remain unresolved. Timer setup is now localized to 5:E268: it sets D988:D989 and the reload bytes D95E/D960; derive its caller arguments and clock selection before assigning a wall-clock duration.

**Live reader follow-up:** the documented wrapper passed a second independent run; six total source samples are 6742/6742 -> raw target 100%. See `docs/maps/battery-live-observations.json`. Next precise work: finish FE GET coverage for a DA4C read route and establish timer divider D988:D989 (ISR 0:011A -> 4:F90A, countdown DA52:DA53 -> 9:BF79). Do not infer exact display timing from 03E8 alone.

**LIVE BREAKTHROUGH 2026-09-30:** ASUS GET FE/EF/F0 reaches internal AA:10 through 12:E431 -> 1508 -> 0:6D00. Three live replies: 6E 84 56 1A 56 1A BA, source words 6742/6742, exact raw target **100%**. Use `tools/Run-SocReadBench.ps1 -Run -BatteryProxy`. See `docs/BATTERY_LIVE_PROXY.md`. DA4C itself remains unread; raw target and filtered display can differ during transitions. Earlier no-live-source statements below are historical. Next: establish runtime DA4C exposure through the FE GET handler or another proven read route.

**GET VCP follow-up:** nine vendor branches at 9:A3A0 checked offline (6,912 executions); no DA4C/D9F7/DCC2 read and no battery-dependent reply. The default 9:EC87 -> 1856 -> 13:6628 is a DDC NULL reply, not a memory proxy. Next: trace the RX routing upstream of 9:EC5B and D990 for a separate read handler. See the battery provenance document.

**Follow-up:** D9F7 is a saved copy of DA4C, with one-byte storage offset 02BE and a 0..100 validator (invalid -> 50). All 256 validator inputs pass. The updater also reaches the ED policy evaluator E703 before display/scaler sink 13:3DE6. See `docs/BATTERY_PERCENTAGE.md`. No live read route is established.

## Latest milestone — 2026-09-30

**Battery OSD provenance identified.** Read `docs/BATTERY_PERCENTAGE.md` first. Internal GPIO I2C AA:10 returns two LE16 words; 0:5A5C converts their ratio, 0:6EB9 filters it, 9:E79E writes **DA4C**, and 10:F8F4 renders digits through 1:D7A1. Exhaustive curve verification passed (65,536 inputs), plus acquisition/filter/render checks. A single source-derived live read via USB returned 2B0A with unchanged buffer after six valid DDC controls. No live SOC value recovered. Next: D9F7 restore provenance and a proven read-only protocol route to DA4C/internal bus. Do not repeat generic scans. Historical priorities below are superseded.

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

OSD text follow-up: FF segment skipping and F8..FE classification are now checked offline (36 and 256 cases). See docs/OSD_TEXT_FORMAT.md and docs/maps/osd-text-format.json. Width/font dispatch branches and FF06 font-byte output are localized. Next: prove width/font table bounds and the menu language validator, then key/state transitions.


OSD font milestone: tools/map_osd_font.py verifies 256 common widths, 2,340 three-byte transfers and 256 loop guards. A full cell uses 27 bytes; 1:DBCA computes 27*glyph + 3*triplet and writes three consecutive bytes to FF06. See docs/OSD_TEXT_FORMAT.md and docs/maps/osd-font-output.json. Pixel packing and peripheral setup remain unresolved. Next: recover menu category/label construction and distinguish EEED/F7B2 resources from E43B/D7A1 text; then navigation and persistence.

OSD language validation milestone: tools/map_osd_text.py now checks 8:7911 for every packed DA03 byte (0..20 accepted, 21..63 -> zero, high bits preserved), selector 32 in 259 getter cases and 6:BA79 masked update tail in all 65,536 old/new byte pairs. The update tail alone does not clamp to 20. See docs/OSD_TEXT_FORMAT.md and docs/maps/osd-text-format.json. Next: full language adjustment/persistence, category handler labels/settings and input/navigation; do not repeat validator discovery.

OSD extension-font milestone: map_osd_font.py now verifies 37,632 width cases (21 indices x seven prefixes x 256 glyph bytes) and 3,096 additional triplet transfers. All 22 extension width/font bases in banks 11/5/2/0 and shared FA dispatch are mapped in docs/OSD_TEXT_FORMAT.md and docs/maps/osd-font-output.json. Five width-table paths use narrow doubling and alias codes separated by 80h; unmatched widths return 12 for indices 0E..13 or incoming R7 otherwise. Mechanical fallbacks do not establish valid tokens. Next: legal glyph/family bounds, font/cell pixel layout and SRAM setup; navigation and language persistence remain unresolved.

OSD event milestone: tools/map_osd_atlas.py verifies all 256 DA6C dispatch inputs at 9:B8B2, all 256 clear-tail inputs at 9:BAE1 and five timer leaf writers (timer 04/05/0C/1A/1C -> display codes 01/02/09/0C/0E). Caller integration is 6:FC3E -> 1472 -> 9:FB97, with call 9:FBA6 into B8B2. See docs/OSD_EVENTS.md. DA6C pending-display-event semantics are strong evidence; raw-key enum, conditional handlers and schedule remain open. Next precise input/control target: 6:FC39 and 9:9CD9, following actual producers before assigning button meanings.

OSD input milestone: initial 2:DF25 classifier reads FF09, FE0D and SFR96h to form D826:D827 (2,048 checks). FF09 inclusive ranges BB..C4/8B..9A/2B..34/4B..54 set 0010/0020/0008/0004; digital zero inputs set 0001/0080. RL6492 reference corroborates ADC_A0 and PORT55 register roles without proving ASUS button wiring. Current DC9E:DC9F, previous DCA0:DCA1, getter F20F, copy F264 and store FDBB were each checked over all 65,536 words. See docs/OSD_INPUT.md and docs/maps/osd-input.json. Next precise priority: DF25 stability from DF91 through E0A2, then E6B6/E20F consumers and physical button/repeat/menu mapping. Do not confuse DCB7&1F system/display-state dispatch with this input word.

OSD full sampling milestone: map_osd_input.py adds 12,304 DF25-through-E0A2 fixtures, including eight retry-cap cases. DCA2:DCA3 caches returned input; absolute ADC delta<2 accepts stability, otherwise saved-sample retries stop at ten. Classification uses saved D828. Direct bit24h suppresses changed nonzero masks except 0001; DA6E bits0/1 are cleared for nonzero raw masks. Tests execute real 5:FBC3 delay early return with CAh=0, so physical timing is not proved. See docs/OSD_INPUT.md. Next precise priority: E6B6/E20F navigation/repeat consumers, bit24h producer and delay timer provenance.

OSD hold milestone: E3A9 caller gate passes only input 0010 to F2C6 (65,536 word checks). F2C6 saves the word, counts 5000 requests or 2500 when 7:F2FC returns 3, resamples until release/count zero, and toggles D9FD.bit6 at zero. All 256 old-byte toggle cases, four full holds and one release-abort fixture pass; other bits are preserved. Tests stop before 15C2 -> 8:DDB3 post-toggle effects and use CAh=0, so save behavior and elapsed timing remain unproved. Key-lock semantics are strong evidence only. See docs/OSD_INPUT.md. Next: 8:DDB3 post-toggle effects, E6B6/E20F/DA6D transitions, repeat and button labels; retain clock/flag24h qualification.

OSD post-toggle handoff milestone: 8:DDB3 calls validator 786B and hands source 01:D9FD, length 0024 (36 bytes), to shared storage writer 01D0. DA87.bit3 clear chooses offset 000E; set chooses 0032+0024*((D9FE>>2)&3), i.e. slots 32/56/7A/9E. All 65,536 DA87/D9FE combinations pass parameter checks; 16 full validator fixtures preserve D9FD.bit6 and reach expected slots. Tests stop before 01D0, so storage medium/completion and physical offsets remain open. This reuses the battery-cache shared storage ABI, not a new guessed protocol. See docs/OSD_INPUT.md. Next precise storage target: 01D0 from 8:DE1A; next navigation targets E6B6/E20F and DA6D/repeat.

OSD storage milestone: tools/map_osd_storage.py verifies 1,656 page plans, 4,096 actual register-frame executions, five complete slot writers, sixteen validator-to-writer fixtures, three timeout paths and 256 mux selectors. Common 01D0 splits the D9FD..DA20 block on 16-byte boundaries, uses A0/address mode1/interface0B, calls 0707 hardware-I2C register output then 14CC -> 0:6C06 polling (at most 50 attempts/page), and returns carry. FE08 is restored to 1 on tested failures; source/remaining length advances before the transfer. EEPROM/write-protect roles remain strong evidence; physical completion/chip identity remain open. All effects occur in offline bytearrays with explicit synthetic peripheral status. See docs/OSD_STORAGE.md and docs/maps/osd-storage.json. Next precise OSD targets: 2:E6B6/E20F navigation, DA6D transitions and adjustment/save callers.

OSD command/repeat milestone: tools/map_osd_commands.py verifies all 65,536 DD54 initial word branches, 105 mode/setting translation fixtures, 139,344 F9FB producer cases, 256 release tails, 256 timer01 flag updates, 145 actual scheduler fixtures and sixteen cancellations. Current/previous input changes publish DA6D and set DA6E.bit4; unchanged inputs consult bits3/2 or request timer01 with argument500/20. Timer01 -> 4:ECA3 sets bit2; default DD54 clears bits2/3 and cancels timer01. Setting01 copies category nibble from DA0C/DA0D/DA0B for inputs4/8/32. Physical buttons and full cadence/lifecycle remain unproved. See docs/OSD_COMMANDS.md. Next precise target: 9:A23E..A26A DA6B/DA6D table calls through2133, alternate8:E49A..E4EB, and post-handler repeat flag resets.

OSD callback milestone: tools/map_osd_handlers.py verifies 376 normal table selections at9:A23E/8FAF and all65,536 alternate setting/command pairs at8:E49A/38C0. Alternate settings5E..A8 select columns0..3; carry-sensitive guards send4/5 toFED6 and reject>=6. 455 distinct explicit callback seeds extend the existing optional CFG traversal from158,425 to166,916 starts (+8,491), with zero overlaps/reserved opcodes and no new indirect sites. Full handler effects remain unproved. Row32 adjustment callbacks lead to9:C031; next9:C0E6 ->19D6/8:B9A9 ->1652/8:8B52. Shared callback prelude1934 ->10:FEB0 is verified in65,536 DA6B/DA83 cases: DBFD..DC00 becomes00/24/04/08; DA6B=0 setsDA83=07, otherwise preserved; R7 is not consumed. Field roles and physical bank identity remain qualified. See docs/OSD_HANDLERS.md and docs/maps/osd-handlers.json.

OSD language preview/apply milestone: tools/map_osd_language_update.py verifies 10,752 row56 preview cases, 65,536 staged-byte writer cases, 256 dirty flags, 4,096 entry comparisons, 512 normal-row32 callback gates, 65,536 generic-setter exclusions and 512 display-event fixtures. Row56 commands1/2 advance/decrease DA48:DA49 modulo21 without changing DA03; command0 selects 9:C63A, whose checked C6B0 tail applies DA49 low6 while preserving DA03 high2 and sets DA69.bit0. Next 167C -> 8:E7E4 produces DA6C=0B for any dirty flags, reaching existing 9:BA6E dispatch. Normal row32 command1/2 calls C031 only in navigation mode, and generic 8:8B52 selector32 is a no-op except scratch; the previous numeric-adjustment next-target assumption is resolved. Full preview/apply drawing and entry transition remain open. See docs/OSD_LANGUAGE_UPDATE.md. Next: row32-to56 transition, 10:CA2A refresh, 9:BA6E save/redraw/dirty clear.

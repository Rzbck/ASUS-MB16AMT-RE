# Next steps — prioritized

## Current mission: complete OSD mapping

The user superseded the power-input investigation with complete static OSD mapping for future modification planning. Start at [docs/OSD_ATLAS.md](docs/OSD_ATLAS.md). Verified layers now include text pointers/segments, common font-byte output, the separate cell-stream renderer, menu category dispatch and menu-text language provenance. The complete map remains unfinished. No hardware mutation or flash is part of this task.

Latest OSD milestone: [docs/OSD_CLOCK.md](docs/OSD_CLOCK.md) verifies 393,216 reset-decision sweeps and300 complete static-clock calls at5:D83F. Effective argument=min(argument,61000); reset/rebase iff snapshot+effective>61000, including wrapped sums; equality does not reset. Active IDs/empty deadlines are preserved, with saturated deadline rebasing. Source-correlated ScalerTimerCheckTimerEvent identity is strong evidence, physical tick rate unmeasured. Next precise targets: **F73D snapshot guard, clock-source/divider setup and equal-current conversion fast path**. Full OSD mapping remains unfinished.

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

## PRIORITY OVERRIDE — direct-machine power-input RE (2026-09-30)

For the current charging/power objective, **read `HANDOFF_DIRECT_MACHINE.md` first**. It supersedes the older recommendation below to keep doing static firmware analysis before touching the machine.

The battery/gauge path is now sufficiently validated for live power measurements. At high brightness with USB video active, the battery has been observed around `-0.70 A` at `~4.15 V`, i.e. about **-2.9 W**, while an aggressive brightness reduction moves battery power toward approximately `0 W`. The immediate engineering question is therefore no longer "where is battery SOC?" but:

```text
How much power/current is actually entering the MB16AMT in the user's current powered-hub setup,
what component/policy limits it,
and can that limit safely be raised enough to eliminate the ~3 W battery deficit at brightness 100%?
```

### P0 now

1. Work directly on the Windows machine and keep the current cabling/hub topology unless a specific later test requires otherwise.
2. Run persistent gauge telemetry (`tools/Run-GaugeWatch.ps1`) while investigating USB/hub/source power state.
3. Inspect Windows/driver/hub/USB-C telemetry for negotiated or available current/power if exposed.
4. Dynamically instrument the official ASUS communication stack (`WinComm.dll`, `WinOperateCScaler.dll`, `WinIspPlugIn.dll`, `Comm_UsbHubI2C.dll`, `Comm_TypeCI2C.dll`, `Comm_RealtekUSB.dll`, Realtek hub libraries) using read-only observation, hooks, debugger, Frida/API Monitor, USBPcap/Wireshark, ETW/ProcMon, or a consolidated x86 harness as appropriate.
5. Identify the actual MB16AMT power-controller/current-limit path empirically. Do not assume the RL6492 reference SY9329/`0xE0` mapping.
6. Correlate live controller/USB observations with battery `I_mA`, `VI_W`, `AP_W`, voltage and temperature while changing brightness/load.
7. Determine whether the deficit is an external source/hub limit or an ASUS/controller policy limit.
8. Only if a specific reversible current-limit setting is proven, test it conservatively with continuous telemetry and a known restore path.
9. Update `HANDOFF.md`, `HANDOFF_DIRECT_MACHINE.md`, `NEXT_STEPS.md` and focused docs/maps with reproducible evidence; keep proprietary binaries out of the public repo and check CI after changes.

### Static PMIC paths now classified as eliminated / non-priority

Do not restart these unless new live evidence specifically points back to them:

- `7:8480`: dominated by internal `DC8B..DC90` bitfield/state work, not a convincing PMIC/I2C helper.
- `9:FBFA`: manipulates scaler/internal registers (`0x0094`, `0x0090`, `0x0091`); upstream immediate `E0` is not evidence of an I2C slave.
- direct decoded search of RL6492-reference Type-C HW-I2C range `0x7F60..0x7F6A`: zero matches in ASUS V020.
- guessed external-bridge PMIC reads at `0xE0`: historical `0x2B0A`; external bridge access is not proof of the internal scaler I2C topology.

Avoid generating another broad candidate report as the next action. The preferred deliverable is a **measured live answer** for VBUS/input-current/current-limit and the component or policy controlling it.

---

**100% -> 99% live validation:** on 2026-09-30, the user reported OSD 99%; three fresh source samples were 6360/6742, 6359/6742, 6359/6742. The exact firmware curve independently returns **99%** for all three (raw ratios 9433/9431 basis points). Brightness was 100, so it is not the source of this result. See [evidence](docs/BATTERY_LIVE_PROXY.md). Direct DA4C access and transient filter timing remain unresolved. Timer setup is now localized to 5:E268: it sets D988:D989 and the reload bytes D95E/D960; derive its caller arguments and clock selection before assigning a wall-clock duration.

**Live reader follow-up:** the documented wrapper passed a second independent run; six total source samples are 6742/6742 -> raw target 100%. See `docs/maps/battery-live-observations.json`. Next precise work: finish FE GET coverage for a DA4C read route and establish timer divider D988:D989 (ISR 0:011A -> 4:F90A, countdown DA52:DA53 -> 9:BF79). Do not infer exact display timing from 03E8 alone.

**LIVE BREAKTHROUGH 2026-09-30:** ASUS GET FE/EF/F0 reaches internal AA:10 through 12:E431 -> 1508 -> 0:6D00. Three live replies: 6E 84 56 1A 56 1A BA, source words 6742/6742, exact raw target **100%**. Use `tools/Run-SocReadBench.ps1 -Run -BatteryProxy`. See `docs/BATTERY_LIVE_PROXY.md`. DA4C itself remains unread; raw target and filtered display can differ during transitions. Earlier no-live-source statements below are historical. Next: establish runtime DA4C exposure through the FE GET handler or another proven read route.

**GET VCP follow-up:** nine vendor branches at 9:A3A0 checked offline (6,912 executions); no DA4C/D9F7/DCC2 read and no battery-dependent reply. The default 9:EC87 -> 1856 -> 13:6628 is a DDC NULL reply, not a memory proxy. Next: trace the RX routing upstream of 9:EC5B and D990 for a separate read handler. See the battery provenance document.

## Active priority — 2026-09-30

1. DONE: D9F7 cache provenance: copied from DA4C, saved/restored at logical storage offset 02BE, invalid values replaced by 50. Host-readable exposure remains unproven.
2. Find an existing read-only route to **DA4C** or internal P5.6/P5.7 I2C AA:10. The external bridge exact read failed 2B0A; do not repeat address sweeps.
3. Establish DA58 update timing, startup/cache validity, and device identity without writes.

The source/conversion/filter/OSD chain is now verified: see `docs/BATTERY_PERCENTAGE.md`. Earlier alternate-renderer search priority is complete. Hardware SOC read access remains the objective.

**2026-09-29 priority override:** live read-only hardware work is now available
in an elevated host. DDC GET works through backend 6 after moving device
enumeration before `InitialDev`; see `docs/LIVE_READ_BENCH.md`.
Do not classify historical `2B08` as a register/ABI failure or repeat closed
VCP/gauge sweeps. A DDC-only control now returns six valid replies from the first
request; keep failed EDID reads out of the default path. Next: derive a specific
read-only SOC request/address from the ASUS
firmware. `NativeRead` is a backend stub; `Read32BitRegEx` writes control
registers and must not be used as a passive snapshot primitive.

## P0 — Build a usable static map of the ASUS V020 image

**ABI milestone completed 2026-09-28:** 741 thunks resolved, old-bank return
mechanism checked, all 27 non-table FFFF occurrences classified. See
`docs/STATIC_MAP.md` and `docs/maps/`. Do not restart the old selector search.
The partial graph has 2,540 decoded thunk-transfer sites; it does not yet resolve
all indirect dispatch or all function boundaries. The next active priority is P1.

Target:

```text
ASUS_RL6492_MB16AMT_Project_AUO_B156HAK02_FF000_20211227_V020_4D38_ELot5_reduce.bin
SHA256 1e75681279bf974d2810e6d2ed91aabbeda35de3fabe1881733aa8a12319cb0c
```

Tasks:

1. DONE: document the `0xE0000` image as 14 x `0x10000` banks;
2. DONE for the common call ABI: verify selectors, gates, thunks and stack return;
3. use separate physical-bank:local and logical-bank:local identifiers; keep boot/partition identity provisional;
4. identify common Realtek library functions by matching instruction/constant patterns against public RL6492 source;
5. produce a symbol notebook/map even if function names are initially inferred.

Deliverable: `docs/STATIC_MAP.md` with bank map + candidate functions.

## P1 — Trace battery percentage from the OSD backward

**8:5FEF contract DONE:** see `SETTING_QUERY.md`; it is a query of stored settings,
not hardware acquisition.

**DA86 path DONE:** see `docs/DA86_TIMER.md`; `DA86` is decremented by user timer
event `0x17`, displayed once per event through `4:F058 -> 1:EAEB`, and followed
by zero/completion cleanup. It is a countdown path, not a SOC path.

**Important pivot:** all three known raw callers of numeric renderer `1:EAEB`
are now explained by non-battery UI:

1. `10:C41E` — generic setting display via `8:5FEF`;
2. `10:E9F7` — generic setting UI scratch via `D82E:D82F`;
3. `4:F058` — `DA86` one-second countdown.

Therefore do **not** keep treating `1:EAEB` / public `OsdPropShowNumber` as the
battery renderer merely because it handles decimal values. The battery OSD is
likely using another numeric/digit/string path.

The OSD remains the ground truth: it can display exact values such as 74, 73,
99 and 100.

### Active P1 tasks

1. Identify the compiled DDC/VCP handler for **confirmed VCP `0xED`** and trace
   its read/set branches into charging and power-management state.
2. From that power-management graph, identify cached battery/charge fields and
   trace their writers back toward I2C/ADC/PMIC/gauge acquisition.
3. Independently enumerate alternate numeric/digit rendering paths used by OSD
   code (direct digit glyph construction, small fixed-width number renderers,
   percent-specific helpers, battery-status strings/icons).
4. Search those alternate renderers for callers whose value is naturally 0..100
   and whose surrounding logic intersects power/charge state.
5. Resolve indirect dispatch only where it blocks these concrete paths.

Look for:

- comparison thresholds near 20 and 100;
- periodic battery/charge refresh events;
- branches tied to charge policy represented externally by VCP `ED`;
- cached power fields updated outside generic OSD setting code;
- I2C/ADC/PMIC primitives reached from those writers.

Do not search only for the ASCII word `battery`; there are no useful plain-text
battery strings in the image.

## P2 — Recover the ASUS board's actual power/battery device

Once a battery-related code path is found, derive from firmware rather than guessing:

- I2C slave address;
- bus/channel;
- register numbers;
- read length/endian format;
- voltage/current/SOC conversion;
- charge-enable GPIO/PMIC action;
- whether SOC is direct from a gauge or computed from voltage/ADC.

Cross-reference with RL6492 public source only after extracting constants from the ASUS image.

Stop condition: do not ask the user to probe a new address until the firmware gives a concrete reason for that address/register.

## P3 — Understand why debug/signature mode is unavailable at runtime

Known state:

- normal `0x6E` works;
- expected signature handshake returns DDC NULL;
- direct `77 55` does not activate `0x6A`;
- `0x6A` remains unavailable.

Investigate statically:

1. whether ASUS V020 compiled signature/debug handlers out, gates them behind a state flag, or routes them through another channel;
2. whether the updater first performs a prerequisite command/reset/power-cycle before the signature handshake;
3. exact call chain inside `WinIspPlugIn.dll` leading to mode detection / mode switching;
4. whether `enumDigitalSignatureType=1`, `enumSWDigitalSignatureMode=4`, and `enumIspMode=1` select a different updater flow than the public Realtek example.

Do not brute-force `77 xx` opcodes.

## P4 — Find a safe read/dump primitive in ASUS tooling

`WinIspPlugIn.dll` exports `DumpFlash`, but the plugin requires updater context pointers.

Goal: reconstruct only the minimum safe initialization needed for a read-only dump.

Tasks:

- map the interface table consumed by `SetCommInterface`;
- identify which callbacks `DumpFlash` actually dereferences;
- map `SetIDev` / `SetUIFunction` requirements;
- determine whether DumpFlash enters ISP/reset mode and whether that is reversible without a write;
- compare dumped bytes against the known V020 package before trusting the primitive.

Do not invoke `ChipEraseFlash` or `IspFlash`.

## P5 — Preserve the proven useful controls

Turn known-good discoveries into small utilities later:

- read/set VCP `ED` charge policy;
- topology-stable black screen overlay + brightness restore;
- safe VCP inventory/snapshot.

These utilities should be separate from experimental firmware probes.

## P6 — Low-priority paths only if static RE stalls

- observe behavior below 20% SOC because ASUS ECO behavior may introduce additional PC communication;
- inspect DisplayLink/ASUS user-mode traffic if a driver/service is found to receive battery events;
- investigate touch/vendor HID only if firmware or USB descriptors connect it to power management.

## Rules for the next runtime experiment

Every new experiment should state before execution:

1. exact hypothesis;
2. exact source evidence supporting it;
3. expected positive result;
4. expected negative result;
5. restore/recovery path;
6. why the same question was not already answered by a previous test.

This should prevent another loop of generic scans and repeated handshakes.

Manufacturer evidence: official MB16AMT manual documents QC3.0 and 5–9 V/2 A. Do not equate charging capability with USB-PD or repeat failed PD reads. Identify source/charger detection, preserving current wiring and no negotiation writes. See docs/POWER_INPUT_LIVE.md.

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

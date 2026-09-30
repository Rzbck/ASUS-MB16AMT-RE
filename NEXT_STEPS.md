# Next steps — prioritized

## Latest live result (2026-09-30)

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

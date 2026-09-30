# Direct-machine handoff — ASUS MB16AMT power-input / charging RE

## Latest live result (2026-09-30)

**16:39 UTC follow-up:** current USB data path is absent (no monitor Realtek/DisplayLink/touch devices; backend count=0, InitialDev=0x2B04). The new guarded `-HubStatus` probe was not sent. Resume it once enumeration returns; no reset or power-cycle was attempted.

See [POWER_INPUT_LIVE.md](docs/POWER_INPUT_LIVE.md): completed supervised brightness/ED campaign, original 100/ED0 restored twice with readback. At ED0, 100% brightness discharges (~1.9–2.6 W observed); 25% and 0% charge positively. ED1 at 100% approaches -7.9 W. These are battery watts, not USB input watts. USB2 high-speed topology and 500 mA DisplayLink configuration descriptor are verified; actual VBUS, input current, PD contract and current limit remain unknown. Next distinct live read: validate active RHub handle/module and test the three-byte RsHub_SmbusGetTPCPDStatus IN request once. No current-limit write is justified yet. Keep injected tracing separate from state-changing campaigns.

**Status date:** 2026-09-30

This handoff supersedes the old "do more static analysis first" recommendation in `HANDOFF.md` / `NEXT_STEPS.md` for the current power-input objective. Static work remains useful only when it directly supports a live experiment.

## Latest direct-machine campaign — preserve this before continuing

See `docs/POWER_INPUT_LIVE_CAMPAIGN_2026-09-30.md` for the full preserved campaign summary.

Key results now established on the live machine:

- OSD/source agreement has now been observed at **100%, 99% and 97%**. At 97%, three reads were `6190/6742`, ratio `9181`, ASUS raw target `97%`.
- Direct-machine timer analysis indicates an approximately **1 second acquisition cadence**; combined with the recovered 13-invocation filter, the displayed percentage changes by about **1 point every 13 seconds** while the raw target remains different. Keep this as strong evidence until the exact timer/divider derivation is preserved in repo artifacts.
- One live state was approximately `4.03 V`, `-0.65 A`, `-2.62 W`, `32.15 C` battery-side.
- Observed USB path: Intel controller -> multiple Genesys hubs -> Realtek hub -> DisplayLink. The active DisplayLink path was reported as **USB 2.0** and its descriptor reported **500 mA**. This is descriptor/request information only, **not** a measurement of total monitor input current.
- `ED=0` versus `ED=1` has a large real battery-power effect. At brightness 100%, one `ED=0` campaign began around `-1.9 W` battery-side, while `ED=1` increased discharge beyond `-6 W` and later approached about `-7.8 W`. Do not subtract these as exact USB input watts because the measurements include filtering/transients and differing sample times.
- With `ED=0`, low brightness can produce positive charging: at 25% the battery balance was already positive, and at 0% about **+1.3 W** was observed battery-side. Returning to 100% returned the battery to discharge.
- Original settings were restored and re-read after testing: **brightness 100%, ED=0**. A first instrumented process had exited before restoration, so subsequent experiments used an independent restore/supervisor path.
- Dynamic traces so far exposed the known ASUS gauge GET traffic and transport but **did not reveal a direct VBUS/input-current/current-limit transaction**.

The unresolved question remains the same: actual live VBUS/input current and the component/policy that limits it at high brightness.

## Objective

Determine why the ASUS MB16AMT battery still discharges while video is active over USB at high brightness, and whether the condition can be improved safely through firmware/configuration so that:

```text
USB video active
+ brightness 100%
+ battery current >= 0
```

Ideally the battery should charge positively at full brightness. First prove whether the limiting factor is firmware policy, USB/hub/source negotiation, PMIC/current-limit configuration, or a hardware power ceiling.

Current physical topology should be left as-is unless a later experiment truly requires otherwise: the MB16AMT is connected through the user's powered hub; the hub is externally powered and marked `5V IN`; the cable is marked `3.1A`. Those markings are not evidence of actual power delivered to the monitor. Measure the live system instead of assuming the negotiated/input current.

## Confirmed live telemetry

Battery fuel-gauge access through the ASUS FE GET proxy is working and strongly matches a TI bq27541-family standard command map. Exact chip identity is still formally unproven, but the telemetry is internally consistent.

Useful tools already in the repository:

```text
tools/Run-SocReadBench.ps1 -Run -GaugeSurvey
tools/Run-GaugeWatch.ps1
```

Observed example at high brightness / USB video:

```text
V_mV ~= 4145..4146
I_mA ~= -701..-706
VI_W ~= -2.91 W
AP_W ~= -2.91 W
flow=DISCHARGING
```

The independent gauge `AveragePower` and `V*I` agree closely. `RemainingCapacity / AverageCurrent` also matched the reported `TimeToEmpty`, which strongly validates the decoded live current/capacity telemetry.

Brightness sweep already showed the battery current moving from about `-2.9 W` at high brightness toward approximately `0 W` at very low brightness. The latest direct-machine campaign extends this: with `ED=0`, 25% brightness was already battery-positive and 0% reached approximately `+1.3 W` battery-side, while returning to 100% returned to discharge.

Therefore the current target remains additional input power / reduced limiting sufficient to eliminate the high-brightness battery deficit, plus margin for positive charging.

## Confirmed battery source / OSD chain

Do not redo this work.

```text
internal GPIO I2C slave 0x55 (7-bit; AA/AB 8-bit)
subaddress 0x10, 4 bytes
-> two LE16 words
-> ASUS ratio/curve
-> stateful filter
-> DA4C displayed battery percentage
```

The ASUS FE/EF/F0 GET proxy can read the live source. `Run-GaugeWatch.ps1` provides richer gauge telemetry including voltage/current/power/capacity/SOC.

`VCP ED` is already proven:

```text
ED=0 -> Charging From NB/PC
ED=1 -> No Charging From NB/PC
```

Do not confuse charge enable/policy with an input-current-limit setting; no such current-setting semantic has been proven yet.

## Latest PMIC / Type-C static work: important eliminations

The RL6492 public reference implementation was used only as a hypothesis source. Several static candidates were investigated and should **not** be recycled as if still promising:

1. `7:8480` is not a convincing PMIC/I2C helper. Its body is dominated by internal XDATA/bitfield work around `DC8B..DC90`.
2. `9:FBFA` is not a convincing PMIC/I2C helper. It manipulates scaler registers such as `0x0094`, `0x0090`, `0x0091`; an immediate `E0` seen upstream is not evidence of an I2C slave address.
3. A direct decoded search for the RL6492 reference Type-C HW-I2C range `0x7F60..0x7F6A` returned **zero direct DPTR references** in ASUS V020. ASUS may use another map, an indirect addressing layer, a separate controller/path, or compile the board differently.
4. The old external bridge `I2CReadEx` attempts against guessed PMIC address `0xE0` returned `0x2B0A`; this does not prove absence of the PMIC because the external bridge route is not the same as internal scaler I2C.

Do not spend the next session generating more broad static candidate reports unless a live observation gives a specific reason.

## Preferred strategy: direct live machine investigation

The next agent has direct access to the Windows machine/screen and should operate autonomously. Prefer consolidated experiments over asking the user to run micro-tests.

### 1. Establish actual USB input power / negotiated capability

Find a way to observe what the monitor/hub path is actually supplying without re-cabling if possible. Investigate Windows USB-C / USB power descriptors, hub port status, USB device tree, DisplayLink/Realtek hub state, vendor APIs, ETW/WMI/SetupAPI/USBView-style data, and any hub/PD telemetry exposed by drivers.

Goal:

```text
VBUS voltage
input current / current limit
negotiated power mode if exposed
port current capability
```

Do not infer this from `5V IN`, cable `3.1A`, or the DisplayLink `500 mA` descriptor.

### 2. Instrument the ASUS updater/communication stack dynamically

Use the official extracted ASUS stack already available locally. Relevant components include:

```text
WinComm.dll
WinOperateCScaler.dll
WinIspPlugIn.dll
Comm_UsbHubI2C.dll
Comm_TypeCI2C.dll
Comm_RealtekUSB.dll
RHubLib.dll / RtHub_USB2I2C.dll
```

Direct dynamic instrumentation is encouraged when read-only / observational:

- x64dbg / WinDbg
- Frida
- API Monitor
- hooks on `GetProcAddress`, WinComm exported calls, plugin resolver slots
- USBPcap + Wireshark if useful
- Process Monitor / ETW where useful
- custom x86 harnesses using the already-proven initialization order

The known correct backend-6 initialization rule is important:

```text
GetDeviceCount BEFORE InitialDev
```

The host executable must be placed where the ASUS communication plugins resolve correctly.

### 3. Look for live changes, not guessed addresses

While `Run-GaugeWatch.ps1` is producing battery current/power, correlate runtime changes with:

- brightness changes
- `ED` charge policy changes where safe
- monitor OSD actions
- video activity / static image
- hub/source state if visible

If ASUS software or a driver queries or writes a power/current setting, capture the exact transaction and reproduce only after its semantics are understood.

### 4. Discover the real power-controller path empirically

Do not assume SY9329 or address `0xE0` merely because RL6492 reference source uses it. Identify the actual MB16AMT path by one or more of:

- runtime traffic from the official software
- USB/driver traces
- dynamic calls into internal communication DLLs
- stable register/value changes correlated with power state
- PCB/chip identification only if it becomes necessary

If an internal read primitive can expose VBUS/current/status without writes, prioritize that.

### 5. Search for current-limit / charge-current policy

Once the actual controller/path is identified, find the control corresponding to concepts such as:

```text
input current limit
charge current
power-path mode
source/sink mode
USB source type
VBUS voltage target
thermal/current throttling
PC/NB-specific conservative limit
```

The key question is whether ASUS intentionally selects a lower limit for PC/USB video operation than the hardware/hub can safely provide.

### 6. Only then consider modification

Do not flash or patch arbitrary values yet. First establish:

- exact current limit now
- source/hub capability now
- controller-supported safe range
- thermal implications
- protection behavior
- whether a runtime setting can prove the concept before firmware modification
- restore/recovery path

A temporary, reversible runtime change is preferable to modified firmware for the first proof-of-concept.

## Safe boundaries

Read-only observation/instrumentation is preferred and may be aggressive.

Do not call destructive flash/erase operations, including `ChipEraseFlash` / `IspFlash`, and do not flash a modified V020 merely to test a hypothesis. Avoid arbitrary PMIC writes. A register write is only justified after its identity/semantics/range are proven and a restore path exists.

Do not use `D6=4`; it logically removes the display and causes Windows topology reflow.

## Working style requested by the user

- Work autonomously on the machine.
- Do not make the user copy/paste a long series of static-analysis commands.
- Prefer one consolidated harness/campaign that initializes once and records all relevant telemetry.
- Use OSD and `GaugeWatch` as ground truth during differential tests.
- If a route fails, pivot yourself rather than asking for repeated generic sweeps.
- Keep evidence classified as `CONFIRMED`, `STRONG EVIDENCE`, `HYPOTHESIS`, `ELIMINATED`.
- Update GitHub continuously with reproducible findings, especially `HANDOFF.md`, `NEXT_STEPS.md`, and focused docs/maps.
- Keep proprietary firmware/vendor binaries out of the public repository.
- Verify CI after repository changes; never state CI is green without checking it.

## Immediate mission

Start from the live machine, not another generic firmware scan.

1. Read the current repo and existing battery/gauge docs/tools, especially `docs/POWER_INPUT_LIVE_CAMPAIGN_2026-09-30.md`.
2. Start persistent gauge telemetry.
3. Inspect the current USB/hub/device power topology and any available negotiated-current information.
4. Instrument the ASUS/Realtek communication stack to identify the actual Type-C/power-controller transactions or relevant internal registers.
5. Build a consolidated read-only runtime harness if needed.
6. Correlate power-controller observations with battery `I_mA/AP_W` under controlled brightness/load changes.
7. Determine whether the high-brightness deficit is due to external source limitation or a firmware/controller limit.
8. If a safe reversible current-limit knob is proven, test it conservatively while continuously monitoring battery current, voltage, temperature, and device stability.
9. Update repository documentation and handoff with exact reproducible evidence.

The desired deliverable is not another list of possible PMIC addresses. It is a measured answer to:

> **How many watts/current are actually entering the MB16AMT in the user's present setup, what component/policy sets that limit, and can it be safely raised enough to eliminate discharge at brightness 100% while USB video remains active?**

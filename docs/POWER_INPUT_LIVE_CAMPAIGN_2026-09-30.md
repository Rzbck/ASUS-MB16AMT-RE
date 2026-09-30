# Direct-machine power-input campaign — 2026-09-30

## Scope

This note preserves the results reported by the direct-machine agent after the direct-machine handoff was introduced. The goal was to characterize why the MB16AMT battery still discharges with USB video active at high brightness in the user's existing powered-hub topology.

These measurements are **battery-side telemetry unless explicitly stated otherwise**. They do **not** constitute a direct measurement of USB input power.

## CONFIRMED — battery percentage cross-check at 97%

Three live source reads agreed with the OSD at 97%:

```text
RM = 6190
FCC = 6742
ratio = 9181 basis points
ASUS raw target = 97%
```

This extends the independent live agreement already observed at 100% and 99% to 97%.

## STRONG EVIDENCE — filter/update cadence

The direct-machine analysis reported that the normal timer path is based on an approximately 1 ms timer base and schedules the battery acquisition path at approximately 1 second intervals.

The already-recovered filter moves the displayed percentage by one point after 13 consecutive differing valid invocations. Combined with the approximately one-second acquisition cadence, this implies roughly **13 seconds per displayed 1% step while the raw target remains different**.

Treat this as strong evidence rather than a final timing proof until the exact timer-clock/divider derivation is preserved in repository analysis artifacts.

## CONFIRMED — live battery telemetry during the campaign

One observed running state was approximately:

```text
VBAT ~= 4.03 V
I_battery ~= -0.65 A
P_battery ~= -2.62 W
T_battery ~= 32.15 C
flow = DISCHARGING
```

This is consistent with earlier GaugeWatch measurements showing a substantial battery deficit at high brightness with USB video active.

## CONFIRMED — observed USB topology / descriptor information

The direct-machine inspection reported the active chain as approximately:

```text
Intel USB controller
 -> multiple Genesys hubs
 -> Realtek hub in/near the monitor path
 -> DisplayLink device
```

The active DisplayLink path was reported as operating at **USB 2.0** during this inspection.

The DisplayLink USB descriptor reported **500 mA**.

Important limitation: this 500 mA value is a USB descriptor/request value. It is **not a measurement of the total current entering the MB16AMT**, and it must not be converted into an assumed monitor input wattage.

No direct PD contract, live VBUS voltage, or live input-current measurement was recovered from the inspected descriptors.

## CONFIRMED — VCP ED has a large real power effect

A controlled comparison used only the already-understood vendor setting:

```text
ED=0 -> Charging From NB/PC
ED=1 -> No Charging From NB/PC
```

At high brightness, disabling Charging From NB/PC (`ED=1`) produced a much larger battery discharge than `ED=0`.

Reported campaign observations included:

```text
ED=0, brightness 100%: beginning of one campaign around -1.9 W battery-side
ED=1, brightness 100%: discharge increased beyond -6 W and later approached about -7.8 W battery-side
```

These values should not be subtracted and labeled as exact USB input power because the gauge is filtered and the measurements include transients / differing sample times. They do establish that `ED=0` allows a substantial real energy contribution from the PC/hub path.

One instrumented process terminated before executing its restore path. The original settings were then restored manually and verified. Subsequent differential testing used a separate supervisor/restore mechanism.

## CONFIRMED — brightness sweep under ED=0

With the charge-from-PC policy enabled (`ED=0`), lowering brightness eventually changed the battery-side balance from discharge to charge.

Reported stable/near-stable observations:

```text
brightness 25%: battery balance already positive (charging)
brightness 0%: approximately +1.3 W into the battery
brightness 100% after return: battery back in discharge
```

The original settings were restored and re-read at the end:

```text
brightness = 100%
ED = 0
```

This establishes that, in the present hub/cable topology, the incoming source can cover the monitor plus some battery charging at low brightness but not the full load at brightness 100%.

## Dynamic instrumentation result so far

The collected traces showed the known ASUS gauge GET traffic and its transport through the Realtek/ASUS stack.

They did **not** reveal a separate transaction that could yet be identified as:

```text
live VBUS measurement
live USB/input-current measurement
input-current-limit read
charge-current-limit read
```

Therefore the actual input power and the component setting the limiting current remain unresolved.

## Current interpretation

### CONFIRMED

- `ED=0` materially increases power available to the system/battery compared with `ED=1`.
- At low brightness the current setup can achieve positive battery charging.
- At brightness 100% the battery still discharges.
- The 500 mA USB descriptor is not sufficient to determine whole-monitor input power.
- The original settings were restored after the campaign.

### NOT YET KNOWN

- actual live VBUS voltage at the MB16AMT power input;
- actual total current entering the MB16AMT;
- exact watts provided by the powered hub to the monitor;
- whether the high-brightness deficit is caused by a hub/source ceiling, USB negotiation, ASUS firmware policy, charger/power-path current limit, or another hardware constraint;
- the real charger / PMIC / power-path controller and its current-limit register(s).

## Next direct-machine priority

Do not repeat generic firmware address scans.

1. Preserve a simultaneous GaugeWatch reference while investigating the source/input path.
2. Identify a direct measurement or vendor-exposed observation of VBUS/input current if possible.
3. Continue dynamic instrumentation of the official ASUS/Realtek communication path, focusing on power-controller configuration rather than the already-solved gauge GET traffic.
4. Look for an exact current-limit / source-type / charge-current policy and prove its semantics before any write.
5. If a reversible current-limit control is identified, compare it against the source/hub capability and only then perform a conservative runtime test with automatic restore and continuous battery/temperature monitoring.

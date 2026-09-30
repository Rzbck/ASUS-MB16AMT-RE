# Live power-input investigation — 2026-09-30

## Measured battery balance

The current powered-hub wiring was retained. The supervised campaign used only
the already understood brightness VCP `10` and charge-policy VCP `ED` controls.
Every control was read back. Eight phases completed; both the native host and
the independent supervisor confirmed restoration to brightness **100, ED=0**.
No PMIC/current-limit setting was changed.

The table gives battery `V*I` over the last 15 seconds of each phase, not USB
input power. Negative means discharge. The gauge AveragePower agreed closely.
Full aggregate data: [power-campaign-summary.json](maps/power-campaign-summary.json).

| Phase | Brightness | ED | Hold | Median battery W | Tail range W |
|---|---:|---:|---:|---:|---:|
| Initial | 100 | 0 | 45 s | -1.918 | -1.923 to -1.918 |
| Charge inhibited | 100 | 1 | 75 s | -7.880 | -7.908 to -7.837 |
| Charge permitted | 100 | 0 | 45 s | -2.428 | -2.683 to -2.236 |
| Brightness sweep | 75 | 0 | 45 s | -0.924 | -1.083 to -0.868 |
| Brightness sweep | 50 | 0 | 45 s | -0.490 | -0.518 to -0.470 |
| Brightness sweep | 25 | 0 | 45 s | +0.456 | +0.415 to +0.480 |
| Brightness sweep | 0 | 0 | 45 s | +1.334 | +1.297 to +1.363 |
| Return | 100 | 0 | 45 s | -2.341 | -2.460 to -2.185 |

**CONFIRMED:** full brightness still discharges with ED=0; ED=1 greatly increases
the battery deficit; low brightness permits positive charging in the same wiring.
The sign crossing occurred between the measured 25 and 50 brightness settings.
An exact steady-state break-even brightness is not established. Several tails
were still moving; the final 100% phase changed -0.275 W across its tail. An
earlier three-minute read-only baseline was approximately -2.61 to -2.62 W.
Thus the initial -1.918 W is not a universal fixed input budget.

The approximately 5–6 W difference between ED policies is a battery-side policy
effect, **not** a direct VBUS power measurement. USB input voltage, input current,
conversion loss, negotiated contract and controller current limit remain unknown.
Neither an external bottleneck nor a firmware bottleneck is proven.

## USB topology and advertised descriptors

`UsbPowerInspect.cs` uses only USB hub GET IOCTLs and descriptor requests, with
packed offsets checked against the installed Windows SDK headers. It reports no
serial strings or device paths. The monitor path observed live was:

```
Intel root -> Genesys 05E3:0608 -> Genesys 05E3:0610
 -> Genesys 05E3:0610 -> Realtek 0BDA:5412
 -> DisplayLink 17E9:437B / touch 0EEF:C000 / Billboard 0BDA:5418
```

The observed monitor data path is USB 2 high speed, not an active SuperSpeed
link. DisplayLink's first configuration declares 500 mA; touch declares 100 mA;
the Realtek hub declares 0 mA and self-powered capability. These declarations
are not current measurements, do not establish the entire monitor's power
budget and must not be added up to infer negotiated capacity. This distinction
follows [Microsoft's configuration descriptor documentation](https://learn.microsoft.com/en-us/windows-hardware/drivers/usbcon/usb-configuration-descriptors).

The captured DisplayLink/Realtek BOS descriptors contain USB extensions,
container/platform and Billboard capabilities, but no Power Delivery capability
types 06/08/09. No readable PD contract was obtained. This does not prove the
absence of PD elsewhere in the system. Logical hub port flags also do not
determine the physical monitor connector type. The inventory queried descriptor
index zero; current configuration was one on the relevant devices.

## Dynamic transport observation

A bounded read-only gauge watch was observed through Frida: 163 `DDCCIWrite`
request calls, 163 `I2CReadEx` response calls and 326 `DeviceIoControl` calls with
code `0x220048`. Loaded transport modules included WinComm, Comm_UsbHubI2C,
RtHub_USB2I2C and RHubLib. This verifies the actual host transport, not the
scaler's autonomous internal I2C bus or the PMIC protocol. The IOCTL buffers
contain pointers and were not decoded as on-wire USB setup packets. WinUSB was
not loaded in these observations. Unknown-ABI exports are listed, not hooked.

An earlier instrumented control campaign terminated unexpectedly during ED=1.
Its cause is unproven; a separate restore process immediately restored and
verified 100/ED0. Those incomplete phases are excluded above. The subsequent
successful campaign used no injected hooks and an independent recovery
supervisor. Keep instrumentation confined to read-only watch processes until
the termination is understood. Raw traces and machine-wide topology stay local.

## Reproduce and next target

Run elevated `tools/Run-GaugeWatch.ps1 -Samples 30` for bounded passive telemetry,
or `-Campaign` for the explicitly state-changing brightness/ED experiment with
restoration. Do not attach an injector to the campaign. Compile UsbPowerInspect
with the Windows .NET Framework C# compiler, then run its executable outside
the repository. `summarize_power_campaign.py LOG --out SUMMARY` publishes only
aggregate electrical measurements, excluding device identifiers and capacities.

The next distinct read target is `RsHub_SmbusGetTPCPDStatus`: offline inspection
establishes a three-byte IN request (`C0 EC`, value `2FD4`, index `1`) with cdecl
arguments `(active_handle, buffer, length=3)`. It has **not been tested live**.
Resolve the actual active RHub module through the lower bridge's function pointer
and guard the output buffer before one bounded test, with valid DDC reads before
and after. Do not repeat the old failed B0/B3 PD helpers without new evidence.
Only a successful, interpretable response can support a controller/input claim.

### Follow-up at 16:38–16:39 UTC

The guarded probe is implemented as `Run-GaugeWatch.ps1 -HubStatus`, pinned to
the inspected lower-bridge and RHub library hashes. The active transfer pointer
selects the owning RHub module, avoiding ambiguity from two loaded DLL copies.
Three-byte sentinel/guard checks and valid DDC transactions bracket the probe.

The first attempt stopped **before the status request**: device count was zero,
and InitialDev returned `0x2B04`. Independent present-only PnP and USB hub GET
enumerations no longer contained the monitor's Realtek, DisplayLink or touch
devices; the upstream Genesys hubs remained. This is an unavailable data path,
not an EC-request rejection. Do not classify this API as a dead end. No reset,
rescan, power command or control mutation was used to recover the device.
Resume the single targeted read when the monitor's USB data devices reappear.

## 17:28–17:30 UTC: USB returned; targeted status read rejected

The monitor USB devices reappeared. Backend 6 enumerated one device and opened
successfully. The hash-pinned RsHub_SmbusGetTPCPDStatus call was executed once:
C0/EC, value 2FD4, index 1, length 3; return 0x1F, output A5-A5-A5 unchanged,
guards intact. Valid DDC brightness replies bracketed the call. This is now a
confirmed unsuccessful read in the current device state, not an absent-device
result. Do not repeat or enumerate nearby requests without new evidence.

A subsequent passive run explicitly read brightness=100 and ED=0, then three
samples at 17:30:19–23 UTC measured 4177 mV, -784 mA, -3.275 W (V*I),
-3.280 W (AveragePower), 28.05 C. ASUS source conversion returned 100 while
the gauge SOC word was 97: these are distinct quantities. No OSD visual reading
was made in this run. Twelve preceding samples also consistently showed about
-3.28 W. No controls were changed in these runs.

There is still no proven input-current-limit setting to optimize at full
brightness. Next firmware target, supporting the live investigation: follow the
non-display consumers of 9:EBE1/EC06 through to an actual power output or source
classification; 13:3DE6 is already eliminated as a display/scaler sink. A usable
input-power conclusion still requires a proven controller read or an independent
VBUS/current measurement, not a subtraction of battery measurements.

## Manufacturer evidence: avoid assuming USB-PD is the charging protocol

The [official ASUS English manual](https://dlcdnets.asus.com/pub/ASUS/LCD%20Monitors/MB16AMT/ASUS_MB16AMT_English.pdf), printed pages 3-7 and 3-10 (PDF pages 25 and 28), explicitly documents QC3.0, a 5–9 V / 2 A rating, and adapter modes of 5 V / 2 A or 9 V / 2 A. It states that the no-charging mode takes less than 100 mA and that charging-from-PC mode can still consume the battery if the USB source is insufficient.

These are manufacturer specifications, not measurements of this unit or wiring.
QC3.0 support does not establish a USB-PD contract. Failed hub PD APIs therefore
do not rule out a separate charging detector/controller. Do not force a voltage,
emulate a charging negotiation or infer the present input power from the label.
The next hardware identification must consider source/charger detection as well
as PD; independently measured VBUS/current would distinguish these hypotheses.

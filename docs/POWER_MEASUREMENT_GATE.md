# Full-brightness power objective: measurement gate

Status: unresolved, no full-brightness improvement demonstrated. This is a
practical gate for the next hardware experiment, not proof that firmware RE can
never expose an input measurement.

## Authoritative evidence

- Passive run at 2026-09-30 17:30:19–23 UTC: VCP 10=100, ED=0;
  battery 4177 mV, -784 mA, V*I=-3.275 W, AveragePower=-3.280 W.
- The earlier controlled sweep produced positive battery current at low
  brightness. It did not achieve the full-brightness objective. Native host and
  independent supervisor restored and verified the initial 100/ED0 controls.
- Windows descriptors declare configuration consumption; they do not measure
  input current. The observed data link was USB2 high speed.
- Known RHub PD reads failed. The distinct active-handle EC/2FD4/1 read also
  returned 0x1F with an unchanged guarded output and healthy DDC before/after.
- The working FE gauge proxy measures battery-side electrical quantities.
  Neither controller identity nor a writable input-current-limit register has
  been established. The known EBE1 return route terminates in display handling.
- The user confirmed that no USB power tester is available.

See [live evidence](POWER_INPUT_LIVE.md), [policy trace](CHARGE_POLICY.md),
and [return-route assertions](maps/charge-policy-return-route.json).

## Why the available measurement cannot locate the limit

Battery power is a net balance. At steady state, USB input and battery discharge
jointly supply the monitor load and conversion losses. We do not independently
know that load, input voltage/current, losses, source capability or current-limit
setting. Many combinations explain the same -3.275 W battery reading. ED changes
the balance but does not make the missing input measurement identifiable.

Consequently neither "the hub provides only X watts" nor "firmware caps current
at Y amps" is supported. A stable 5 V reading alone would not settle that question
either; a source limit and a conservative sink policy can look alike.

## Smallest useful physical observation

If a suitable instrument becomes available, establish its documented voltage,
current and USB data pass-through compatibility before insertion. Use passive
measurement only: no QC/PD trigger, voltage forcing, electronic load or protocol
emulation. Do not open the monitor. Insertion requires a physical reconnection
and is not performed by this software task.

1. Capture the existing USB topology, brightness and ED, plus a stable battery
   baseline. Preserve the user's original settings.
2. Measure at the monitor-side input, retaining the existing source, hub and
   cable as far as physically possible. Identify the measurement location and
   account for instrument/adapter voltage drop.
3. Verify video, touch, USB enumeration and gauge reads still work. A changed
   link or disturbed power path invalidates a same-setup comparison.
4. At brightness 100 and ED=0, collect synchronized VBUS, input current and
   battery voltage/current/power for at least 120 seconds, extending the hold
   if the tail is still changing. Retain measurement ranges and uncertainty.
5. Only if the baseline remains comparable, use the already supervised
   brightness/ED controls for a matched comparison and verify restoration.

The initial result establishes actual input power at the measurement point.
Voltage droop correlated with load supports a source/cable-path limitation but
does not identify a specific component. Stable voltage and limited current do
not by themselves distinguish source advertisement from sink policy. Further
source specifications or a justified controlled comparison may still be needed.

## Conditions for resuming controller experiments

Resume a new software hardware-read experiment only with new evidence defining
its device, route, request ABI, output validation and read-only semantics. Do
not retry the closed requests or scan arbitrary addresses. Offline analysis of
generic setting-query consumers and packed-state copies remains possible, but
is not a substitute for input-power evidence or permission for register writes.

No current-limit experiment is justified until controller/register identity,
units, supported range and restoration are proven. The user preference to
protect the monitor takes precedence over obtaining a speculative result.

# Read-only battery gauge telemetry survey

## Purpose

The verified ASUS `GET FE/EF/F0` proxy can read the monitor's internal software-I2C target at 7-bit address `0x55` (`AA/AB` in 8-bit form). The already-confirmed battery source reads four bytes from register `0x10` and returns two little-endian words used by the ASUS firmware as remaining/full capacity inputs.

The observed `0x10` / `0x12` layout matches the public Texas Instruments **bq27541-family** standard command map exactly:

- `0x06` Temperature (read-only, 0.1 K)
- `0x08` Voltage (read-only, mV)
- `0x0A` Flags (read-only)
- `0x0C` NominalAvailableCapacity (read-only, mAh)
- `0x0E` FullAvailableCapacity (read-only, mAh)
- `0x10` RemainingCapacity (read-only, mAh)
- `0x12` FullChargeCapacity (read-only, mAh)
- `0x14` AverageCurrent (read-only, signed mA)
- `0x16` TimeToEmpty (read-only, minutes)
- `0x18` TimeToFull (read-only, minutes)
- `0x1A` StandbyCurrent (read-only, signed mA)
- `0x1C` StandbyTimeToEmpty (read-only, minutes)
- `0x1E` MaxLoadCurrent (read-only, signed mA)
- `0x20` MaxLoadTimeToEmpty (read-only, minutes)
- `0x22` AvailableEnergy (read-only)
- `0x24` AveragePower (read-only)
- `0x26` TimeToEmptyAtConstantPower (read-only, minutes)
- `0x28` InternalTemperature (read-only, 0.1 K)
- `0x2A` CycleCount (read-only)
- `0x2C` StateOfCharge (read-only, percent)

This is currently a **command-map candidate**, not a proven exact chip identity. The live survey is designed to test the mapping without using `Control()`, DataFlash, manufacturer access or any write command.

Public reference: Texas Instruments bq27541-V200 / bq27541-G1 standard data command table.

## Safety boundary

`tools/GaugeSurvey.cs` only sends the already-verified ASUS **GET** proxy with fixed four-byte reads starting at documented read-only standard-command addresses. It deliberately avoids:

- `0x00 Control()` and `0x02 AtRate()` because those are R/W commands;
- DataFlash / block-control registers;
- FE SET branches;
- Set VCP;
- debug / ISP / reset / firmware programming;
- arbitrary address sweeps.

Each proxy request is preceded by a known GET-VCP brightness reply. The exact reproduced stale payload `02 00 10 00` is rejected, along with checksum, framing, sentinel and guard failures.

## Run

From an **elevated PowerShell** after pulling the current repository:

```powershell
git -C $repo pull --ff-only
& "$repo\tools\Run-SocReadBench.ps1" -Run -GaugeSurvey
```

The important output lines begin with `GAUGE`.

Expected summary shape:

```text
GAUGE TEMP_raw_0p1K=... TEMP_C=... VOLT_mV=...
GAUGE FCC_mAh=... AVG_CURRENT_mA=...
GAUGE TTE=... TTF=...
GAUGE CYCLE_COUNT=... GAUGE_SOC_pct=...
GAUGE_PROFILE_EVIDENCE=...
GAUGE_SUMMARY voltage_mV=... avg_current_mA=... battery_power_est_W=... flow=... RM_mAh=... FCC_mAh=... gauge_soc_pct=... asus_raw_target_pct=...
```

For the bq27541 command convention, negative `AverageCurrent` means battery discharge and positive means charge. The derived `battery_power_est_W` is simply `Voltage * AverageCurrent`; it is useful for comparing operating conditions, not for claiming USB-input power.

## What this test should answer

If the map matches live hardware, the highest-value signal is `AverageCurrent` at `0x14`. It can directly show whether the battery is charging or subsidizing the display load while changing:

- brightness;
- USB video activity;
- `Charging From NB/PC` policy;
- power source / cable / host.

That measurement should be combined later with USB input voltage/current from an external meter or a proven Type-C/charger telemetry path before concluding that firmware alone can increase charging power.

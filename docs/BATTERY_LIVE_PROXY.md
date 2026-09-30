# Live battery source read via ASUS FE proxy

## Confirmed on hardware, 2026-09-30

The normal DDC transport reaches an ASUS-specific handler **before** the standard VCP dispatcher:

```text
9:EC3D -> 9:EC56 -> thunk 1844 -> 12:E431
D993 = FE, D992 = 01 (GET)
D994 = EF, D995 = F0
 -> 12:E95A -> EF39: register from D997, length from D998
 -> R7=AA, R5=1, R2:R3=0010, output 01:D9C2, length 4
 -> thunk 1508 -> 0:6D00 (the battery's internal software-I2C read)
 -> reply 6E 84 [four source bytes] [XOR checksum]
```

The fixed payload to `DDCCIWrite(6E,51,7,...)` is **01 FE EF F0 00 10 04**. WinComm constructs framing and checksum. This is a GET command, not Set VCP, and needs no debug/ISP/mode change. A raw I2C read of seven response bytes through the working USB backend obtains the reply.

Three consecutive hardware replies were:

```text
6E 84 56 1A 56 1A BA
u = 0x1A56 = 6742
v = 0x1A56 = 6742
x = u*10000/v = 10000
firmware raw target percentage = 100
```

Each request followed a fresh, validated brightness GET control. Guards remained intact, all checksums passed, and all three replies agreed. This is a measured live battery-source ratio, not an arbitrary byte matching the user's reported 100%.

## Command

From an elevated PowerShell at the repository root:

```powershell
.\tools\Run-SocReadBench.ps1 -Run -BatteryProxy
```

It initializes once, validates transport, performs three bounded source reads, and releases the device. Output explicitly labels `raw_target_percent` and `displayed_DA4C=NOT_READ`. The exact firmware curve is applied. No sweep, reset, ISP, flash, storage write or Set VCP is performed.

## Crucial validity checks

The firmware proxy **ignores the I2C success flag**. If internal I2C fails, it can return old TX payload bytes with a valid new checksum. The host therefore primes TX with a brightness reply immediately before each request and rejects its payload `02 00 10 00`, as well as bad framing/checksum, unchanged buffers and zero denominators. This guards against the reproduced failure case; transport framing alone is insufficient.

`tools/trace_battery_proxy.py` executes the actual dispatch and reply construction offline with successful/failed I2C mocked at 1508, and stops before transmission at 1298. It checks the exact slave/register/length/pointer ABI and bounds the caller's XDATA writes to scratch and TX buffers. See `maps/battery-proxy.json`. The real read routine manipulates bus GPIO and may set DCC0=1 when DA63=1, as part of the existing read path; it does not run the acquisition wrapper's failure recovery pin toggle.

## What remains

This command reads the **source of the percentage** and computes the unfiltered target. It does not directly read DA4C, and cannot reproduce unknown prior filter/cache state during transitions. The last user-reported 100% agrees with the live raw target, but exact live displayed percentage still requires a DA4C read or separately validated synchronization with the filter.

Fuel-gauge identity and units of the two words remain unproven. No claim that 6742 is mAh is required for the ratio proof.

Next: investigate other FE GET branches for runtime memory exposure, while keeping the verified source reader usable. Do not execute FE SET branches or assume all commands bearing GET are free of writes.


## Repeatability and remaining display timing

The documented wrapper was tested end to end in a second run at 06:02:35Z, after the first run at 05:58:56Z. All six source samples agreed. Sanitized observations are in [battery-live-observations.json](maps/battery-live-observations.json).

Static timing facts: `9:BF65` checks the DA52:DA53 countdown, reloads it with 03E8 at `9:BF6F`, then calls the updater at `9:BF79`. `4:F925..F93F` decrements this word; common timer ISR `0:011A` calls that routine through 0DDC. The ISR divider uses D988:D989 and D92B:D92C. Until the divider/reload clock is established, 1000 ticks must not be presented as a proven duration. `9:F298` provides an additional updater call when DA4C=0.

The other decoded FE GET paths inspected so far return settings/constants, diagnostic data, or stored data; the EF/F0 branch is the proven live source path. No runtime DA4C proxy has yet been established. The next precise tasks are to finish that FE GET coverage and derive the timer divider, so a filtered estimate cannot be mistaken for an actual display read.


## Independent 100% -> 99% validation

At 2026-09-30 06:49:38Z, following the user's report that the OSD had dropped to 99%, three fresh source reads returned:

| Source reply | u | v | Integer ratio x | Firmware target |
|---|---:|---:|---:|---:|
| 6E 84 D8 18 56 1A 36 | 6360 | 6742 | 9433 | 99 |
| 6E 84 D7 18 56 1A 39 | 6359 | 6742 | 9431 | 99 |
| 6E 84 D7 18 56 1A 39 | 6359 | 6742 | 9431 | 99 |

For this curve segment the target is `(x+550)//100`, so a raw ratio around 94.3% correctly produces the observed 99%. The numerator changed between samples; the denominator remained 6742. All source frames passed checksum/guard/stale-payload checks. Brightness controls read 100 during this run, independently excluding confusion with that VCP value.

This confirms live variation in the previously traced battery source and agreement of the firmware conversion with two reported OSD values. It does not establish the duration of transient display lag or directly read DA4C. These captured inputs are now included in the original-instruction acquisition and proxy regression tests.

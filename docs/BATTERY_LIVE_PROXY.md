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


## Independent 97% validation and timing follow-up

At 2026-09-30 07:00:34Z the user reported OSD 97%. Three validated replies were `6E 84 2E 18 56 1A C0`: u=6190, v=6742, x=9181, converted target `(9181+550)//100 = 97`. The captured input is covered by the original-instruction acquisition and proxy checks. Live agreement now spans 100%, 99% and 97%, without modifying charging or brightness settings.

### Timer evidence

`4:F3B3` passes R6:R7=0001 to 16E2 -> `5:E268`. Executing this setup offline for its three clock branches yields divider D988:D989=0001, intermediate D98C:D98D=03E8, and reloads E373/F6E2/FB56. These correspond to subtracting 7308/2333/1193 counts from FFFF. TL1/TH1 receive the matching reload bytes. `4:F90A` decrements DA52:DA53 with zero saturation (1,002 tested inputs); `9:BF6F` reloads 1000 and calls the battery updater.

The instruction sequence matches public `ScalerTimer1SetTimerCount(WORD usTimerMs)` in `Kernel/Scaler/ScalerCommonFunction/Code/ScalerCommonTimerFunction.c:1074`, reference revision 3d38340ec8518a8888fd5d8dbb181c2a7418e11c. That function takes milliseconds and uses the same 1000 multiplier, divider, clock selection and reload structure. Therefore the intended normal acquisition cadence is approximately one second; a continuing difference moves the display filter one point every 13 normal calls, approximately 13 seconds. **Strong evidence for nominal timing**, not a physical timing measurement or a guarantee under every state: DA58 can defer acquisition, zero percentage has another update path, and interrupt/scheduler delay is not measured.

Reproduce with `tools/trace_battery_timing.py`; see [battery-timing.json](maps/battery-timing.json).

### FE GET routing coverage

`tools/trace_fe_get_routes.py` checks all 65,536 combinations of the two FE GET selector bytes, plus eight metadata gate cases, stopping at service entrypoints. The only primary selectors reaching services are 10, 16, CC, E1, E9 and EF. EF/F0 reaches AA internal I2C, EF/F1 reaches slave 16. Other branches reach setting replies, fixed metadata, diagnostic logs, or the storage dispatcher F684.

No direct DA4C/D9F7/DCC2 read occurs in this dispatch. This is not a proof about the complete transitive services: the checks stop before their execution. [fe-get-routes.json](maps/fe-get-routes.json) preserves exact selector destinations. The remaining precise cache-read candidate is the transitive storage/diagnostic service path, especially `12:F684`; do not send unverified selectors to hardware merely because they are under GET.

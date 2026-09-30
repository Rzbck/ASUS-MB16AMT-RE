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

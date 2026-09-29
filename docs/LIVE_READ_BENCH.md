# Live transport validation, 2026-09-29

SOC remains unresolved. The earlier OSD observation of 98% is historical,
not the current value and not a result of these reads.

## Confirmed on hardware

Elevated host, pinned WinComm image, backend ID 6 (`Comm_UsbHubI2C.dll`).
`InitialDev=0`; one bridge detected. The live WinComm resolver points to:

| Export | Backend RVA |
|---|---:|
| I2CRead | 1450 |
| I2CWrite | 1410 |
| NativeRead | 1800 |
| InitialDev | 12E0 |
| GetDeviceCount | 1840 |

**Enumerate BEFORE opening.** Calling `GetDeviceCount` after `InitialDev`
invalidates the lower bridge state. Before correction all reads failed with
`2B08`; after moving enumeration before open, DDC GET requests and reads work.
This invalidates interpreting historical `2B08` as an address/ABI rejection.

At 06:01 UTC, `DDCCIWrite(6E,51,2,[01,10])` followed by
`I2CReadEx(6E,00,11,out,0)` produced three checksum-valid brightness responses,
current 0 / maximum 100, matching three Windows physical-monitor GET VCP reads.
At 06:02 UTC, reversing the two DDC reader tests produced three valid replies
through `DDCCIRead(6E,00,11,out)` instead. Output sentinel buffers changed and
both guard regions stayed intact. These are brightness controls, **not SOC**.

The first DDC reply after failed EDID tests was malformed in both runs. The raw
reader captured `88 02 00 10 00 00 64 00 00 C0 00`, missing the initial `6E`.
The vendor parser returned `0E` and left the caller's sentinel unchanged.
Do not silently prepend a byte or accept this as a valid response. Exact cause
of the first-frame alignment failure remains unproven.

Both EDID reads (`I2CRead` and `I2CReadEx`, slave A0, subaddress 0, 128 bytes)
returned `2B0A` with unchanged buffers. No EDID snapshot was recovered.

## Static explanation and restrictions

All VAs below use the preferred image base 10000000.

- Backend `GetDeviceCount` 10001840 calls enumeration 10002FD0, which invokes
  lower `AvailableDevices` 10002070. That lower routine calls through its
  device handle and clears global handle 1001E7A4 at 100020B8 / 1000210D.
  It is not a side-effect-free count accessor.
- Backend read helper 10003230 returns `2B08` when lower `SetBusSpeed` fails,
  before calling `ReadI2C`; `2B0A` identifies the later failed read.
- Backend `NativeRead` 10001800 is a stub: no device call and no output store.
  It cannot provide a memory snapshot on backend 6.
- WinComm `ReadRegEx` 10004530 in mode 2 uses direct I2C reads for FFxx,
  but other pages may call `WriteReg(9F,page)` then use address/data ports.
  An address such as D833 is not proof of MCU XDATA access.
- WinComm `ReadSysDevice` 10004C30 writes the configured system-device slave
  at subaddresses 02 and 44/45 before reading. This is not a new passive bus.
- `Read32BitRegEx` 10006A60 in mode 2 calls 10006F80, which reads/modifies/
  writes FDE5 and writes FDD0..FDD3. Do not run it as a pure read primitive.

No debug switch, ISP entry, programming, reset, SET VCP, register sweep or
arbitrary selector write was issued by this bench. USB bridge configuration
and fixed DDC GET request transmission are part of the vendor read transport.

## Reproduce

From an elevated PowerShell in the repository:

```powershell
./tools/Run-SocReadBench.ps1 -Run
```

The wrapper builds an x86 host, preserves vendor dependency directories, runs
checksum/sentinel self-tests, and bounds the live process to 60 seconds. No
arguments performs no device I/O. Vendor binaries and full local logs stay out
of the repository. Successful transport does not establish a SOC primitive.

WinComm SHA256: d237f4fbe3ab3acfc4170558785b422aeaea055627522510105f5517b0d78739

Comm_UsbHubI2C SHA256: 90f61a228eb4c58dfca72e597e5366549483022765e7cb4c49b21fe883a1907f

RtHub_USB2I2C SHA256: 1fa6235d6a00c139ed2827c4a6f0de382796b5435a788b4bf1b3e38bfa032a7d

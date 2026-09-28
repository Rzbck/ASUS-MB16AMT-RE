# Protocol notes

## Address summary

```text
0x6E  normal DDC/CI / scaler-facing address observed on MB16AMT
0x6A  Realtek debug slave from WinComm autodetect/reference code; NOT reached yet
0x94  ASUS updater ISP slave from IspSetting.ini / WinComm
0x96  continuous ISP slave reported by WinComm
0xE0  SY9329 PMIC address in RL6492 reference designs; not reachable on tested MB16AMT bridge path
```

## WinComm plugin discovery

`WinComm.dll` is x86 and discovers communication modules relative to the **host executable path**. A reliable test harness therefore places the compiled x86 host in the extracted ASUS updater root.

Working initialization sequence:

```text
Initiallize()
SetCommByID(6)
InitialDev()
AutoDetectSlaveAddr()
...
ReleaseDev()
```

Observed working state:

```text
Comm modules: 3
CommID: 6
Devices: 1
AutoDetect: 0
ISP slave: 0x94
continuous slave: 0x96
debug slave: 0x6A
DebugMode: 2
```

## DDC/CI framing

`WinComm!DDCCIWrite(slave, sub, len, payload)` constructs a DDC/CI frame and adds checksum internally.

`DDCCIRead` validates the DDC response and checksum and copies the response into the caller buffer.

A DDC NULL reply was repeatedly observed as:

```text
6E 80 BE
```

This is a valid NULL response, not battery data.

## Supported VCP experiment

Raw Get VCP sweep was performed for `00..FF`. Only responses with result code `0x00` should be treated as supported. Unsupported responses can still carry stale-looking values and must not be interpreted as sensors.

Confirmed vendor control:

```text
VCP ED
max=1
0 = Charging From NB/PC
1 = No Charging From NB/PC
```

Confirmed non-battery control:

```text
VCP E3
allowed: 00 19 32 4B 64
=> decimal 0,25,50,75,100
```

E3 remained at 100 while actual battery SOC changed, so it is not SOC.

## Realtek signature/debug reference protocol

Public RL6492 reference source defines a signature DDC/CI path with:

```text
sub-address       0x71
command type      0x77
handshake request 0x11
handshake reply   0x22
pass byte         0x90
change-to-debug   0x55
```

Reference debug mode uses slave `0x6A` and normal DDC/CI uses `0x6E`.

Important: this protocol structure exists in reference code, but the tested MB16AMT did not produce the expected handshake response and did not switch to 0x6A when sent `77 55` directly.

## Realtek debug register commands from public source

Reference `ScalerCommonDebug.c` defines:

```text
0xBA = write registers
0xBB = read registers
max debug data count = 24 bytes
```

Read command inputs include a 16-bit address, length, auto-increment flag, and additive checksum. The handler reads through `ScalerGetByte(address)`.

This is potentially a very powerful XDATA primitive **only after debug mode is genuinely active**. Do not keep sending 0xBB/0x3A to 0x6A while the device remains in normal 0x6E mode.

## ASUS updater plugin facts

`WinIspPlugIn.dll` exports:

```text
ChipEraseFlash
DumpFlash
EnterISPModeExport
GetFWInfo
GetKeyFromFlash
GetUserDefinedInfoFromDDCCI
IspFlash
RecordFWVersion
ResetMCUExport
SetCommInterface
SetIDev
SetUIFunction
```

The exported plugin API expects context/interface pointers supplied by the updater. Calling complex exports directly without reproducing that initialization is unsafe/unreliable.

`SetCommInterface` stores a pointer to a function table rather than simply accepting `WinComm.dll` itself.

## Known Realtek/ASUS mode-switch experiments

### Handshake `77 11`

Repeated result in normal runtime:

```text
write succeeds
read returns DDC NULL: 6E 80 BE
```

No `77 22 90` was observed.

### Direct `77 55`

Result:

```text
before: 0x6E accessible
after:  0x6E still accessible
0x6A debug write fails (0x2B09)
```

So the normal running monitor did not switch to Realtek debug mode.

## Safety note

Mode-switch and ISP protocol knowledge is recorded here to prevent rediscovery. It is **not** a recommendation to invoke flash/erase/reset operations. The current project priority remains read-only analysis.

# Firmware package and static-analysis notes

## Official ASUS package used

```text
ASUS_MB16AMT_FW.zip
size:   10,487,921 bytes
SHA256: 8c070d21a9ff95ab9916941fc77c41e913c727d92ac891dca2e26662e18e71dc
```

Outer ZIP contents:

```text
MB16AMT series FW update SOP_V1.0.pdf        296,948 bytes
OneKeyUpdate_MB16AMT_20211227.sfx.exe     10,348,184 bytes
```

The SFX contains a RAR payload beginning around file offset `0x4CC00`.

## Extracted updater payload

Key files and sizes:

```text
ASUS_RL6492_MB16AMT_Project_AUO_B156HAK02_FF000_20211227_V020_4D38_ELot5_reduce.bin  917504
OnekeyUpdate.exe                                                                  3360256
WinComm.dll                                                                       1881600
WinOperateCScaler.dll                                                             2147840
WinSignatureVerify.dll                                                            3915776
PlugIn/WinIspPlugIn.dll                                                           2262528
PlugIn/Option/WinIspSettingPlugIn.dll                                             2140160
PlugIn/Flash.dat                                                                    40046
PlugIn/IDCodeList.bin                                                                5003
Comm/Comm_GLHubI2C.dll                                                             250368
Comm/Comm_RealtekUSB.dll                                                           523264
Comm/Comm_TypeCI2C.dll                                                             229376
Comm/Comm_UsbHubI2C.dll                                                            235520
Comm/GLHub/GLHub.dll                                                              1953280
Comm/UsbHub/RHubLib.dll                                                           2301440
Comm/UsbHub/RtHub_USB2I2C.dll                                                      125440
IspSetting.ini                                                                        2465
IspLog.txt                                                                             3326
IspResult.txt                                                                            15
```

The proprietary ASUS package and binaries are intentionally not committed here.

## Scaler image

```text
file: ASUS_RL6492_MB16AMT_Project_AUO_B156HAK02_FF000_20211227_V020_4D38_ELot5_reduce.bin
size: 917,504 bytes = 0xE0000
SHA256: 1e75681279bf974d2810e6d2ed91aabbeda35de3fabe1881733aa8a12319cb0c
```

Embedded marker:

```text
#01V020AUO B156HAK02.0URLMB16AMT
```

The 0xE0000 image has repeated 64 KiB bank structure. At bank boundaries the byte patterns look like 8051-family jump/vector code (`0x02` / LJMP style), consistent with a banked Realtek scaler firmware.

No useful plain ASCII strings for `battery`, `charge`, `SOC`, `percent`, etc. were found in the image, so the battery path likely needs control-flow/data-flow RE rather than string chasing.

## IspSetting.ini

Relevant values from the package:

```ini
[ISP_Action]
enumActionType=6

[ISP_DualBank]
enumDigitalSignatureType=1
enumSWDigitalSignatureMode=4
enumBootCodeType=1
enumIspMode=1
bWaitCopyBank=0
ulTimeWaitCopyBank=8000
ulTimeAfterCommand=200
ulCommandRetryCount=10
ulTimeAfterReset=10000
bReleaseDeviceAfterReset=0

[ISP_Basic]
bAutoDetectSlave=1
ucSpecifiedSlave=148
bIspBeforeAcOn=1
ulTimeBeforeAcOn=2500
bResetMcu=1
ulIspSpeed=200
ulSwitchTToRomCodeDelay=800

[Communication]
enumCommID=6
```

`ucSpecifiedSlave=148` decimal is `0x94`.

The `[ISP_Fw]` section contains 11 bank entries (`0..10`) and stale/internal build paths for an unrelated HP-named signing image. Do not interpret those build paths as the actual MB16AMT firmware source tree.

## Historical IspLog.txt

The package carries updater logs from 2021.

Successful run, 2021-08-04:

```text
Enter ISP mode Success!
ScalerType: 0x2f
IDCode0: 0xce
IDCode1: 0x23
Flash IDCode: c2 20 14 13 ...
Flash Name: MX/KH25L800X
Bank 10 ... Bank 0 ISP Success
Isp time: 160453 ms
```

Other runs on 2021-07-27 and 2021-11-15 failed entering ISP with error `0xA`.

Current `IspResult.txt` says:

```text
IspResult:0xa
```

## WinIspPlugIn.dll

Observed exports:

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

Important implementation notes:

- plugin functions rely on updater-supplied interface/context pointers;
- `SetCommInterface` stores a function-table pointer;
- `SetIDev` and `SetUIFunction` also populate globals/context;
- therefore calling exports like `GetFWInfo`, `DumpFlash`, or `EnterISPModeExport` directly by P/Invoke is not equivalent to the updater's normal setup.

Do not call destructive exports during exploratory work.

## Firmware-modification status

No modified firmware has been flashed.

Before any modification work, establish all of the following:

1. deterministic read/dump of the exact running firmware;
2. checksum/signature layout;
3. dual-bank semantics and bank-selection tags;
4. reliable recovery path if the active image fails;
5. exact hardware revision/panel match.

Until then, firmware work should remain static analysis only.

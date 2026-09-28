# Sources and provenance

## ASUS firmware package

The RE session used the official MB16AMT firmware-update package supplied by the user:

```text
ASUS_MB16AMT_FW.zip
SHA256 8c070d21a9ff95ab9916941fc77c41e913c727d92ac891dca2e26662e18e71dc
```

The package contains the ASUS SOP PDF and `OneKeyUpdate_MB16AMT_20211227.sfx.exe`. The actual firmware/update binaries are proprietary and are not redistributed in this repository.

## Public Realtek RL6492 reference source

Primary public reference repository discovered during research:

- https://github.com/Kingdomwhisky/RTD-Scaler-TEST

High-value files:

- `Kernel/Scaler/RL6492_Series_Scaler/Code/RL6492_Series_Mcu.c`
- `Kernel/Scaler/ScalerCommonFunction/Code/ScalerCommonDebug.c`
- `Kernel/User Common Function/Code/UserCommonSignDdcciFunction.c`
- `Kernel/User Common Function/Header/UserCommonSignDdcciDefine.h`
- `User/Device/Code/TypeC_Pmic_SILERGY_SY9329.c`
- `Pcb/RL6492/LQFP_156/RL6492_PCB_EXAMPLE_156_PIN.h`

Useful facts derived from this source include:

- normal Realtek DDC/CI address `0x6E` and debug address `0x6A` in the reference implementation;
- signature DDC/CI command family (`0x71`, command type `0x77`, handshake/debug opcodes);
- scaler debug commands `0xBA` / `0xBB` and 16-bit register-address semantics;
- RL6492 reference-board use of a Silergy SY9329 PMIC at `0xE0` with battery/VBUS ADC registers.

### Important provenance warning

This is **reference Realtek code**. It is not an ASUS MB16AMT source release and does not prove the MB16AMT uses the same PMIC, compile-time options, PCB routing, or enabled debug/signature mode.

The failed `0xE0` PMIC probe and failed `0x6A` debug switch are concrete examples of why reference-code facts must be verified against the ASUS unit.

## Local/user experimental evidence

The conclusions in this repository also come from controlled tests against the user's physical MB16AMT under Windows, including:

- supported VCP enumeration;
- charging-policy A/B comparison;
- real battery SOC drop comparisons;
- WinComm/ASUS updater initialization;
- read-only I2C probes;
- static analysis of the extracted ASUS updater DLLs and scaler image.

See `docs/EXPERIMENTS.md` and `docs/DEAD_ENDS.md` for the results that should be treated as device-specific evidence.

## Source-handling rule for future work

Prefer this evidence order:

1. actual MB16AMT runtime observation;
2. actual ASUS MB16AMT firmware/updater static analysis;
3. public RL6492 reference source;
4. generic chipset/fuel-gauge assumptions only as hypotheses.

Never promote a reference-board constant to an MB16AMT fact without testing or finding the same constant/path in the ASUS firmware.

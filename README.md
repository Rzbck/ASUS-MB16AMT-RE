# ASUS MB16AMT reverse engineering

Reverse-engineering notes for the **ASUS ZenScreen Touch MB16AMT** (Realtek **RL6492** scaler), with a current focus on:

- reading the internal battery state-of-charge from Windows;
- controlling the monitor's USB charging policy without disrupting display topology;
- documenting the ASUS/Realtek firmware-update and DDC/CI paths;
- keeping future firmware work reproducible and safe.

> Start with **[HANDOFF.md](HANDOFF.md)**. It is the canonical state for the next session / next agent.

## Current high-confidence findings

- Monitor: ASUS MB16AMT, MCCS model string `ASUS MB16AMT`, monitor ID `AUS1661`.
- Scaler: **Realtek RL6492**.
- Official ASUS firmware image found: `ASUS_RL6492_MB16AMT_Project_AUO_B156HAK02_FF000_20211227_V020_4D38_ELot5_reduce.bin`.
- Firmware image size: `917504` bytes (`0xE0000`, 14 x 64 KiB banks).
- Firmware string: `#01V020AUO B156HAK02.0URLMB16AMT`.
- Windows updater uses ASUS `WinComm.dll` with **CommID 6** and `Comm_UsbHubI2C.dll`.
- Normal DDC/CI/scaler address observed: `0x6E`.
- ASUS updater configuration specifies ISP slave `0x94` and continuous ISP `0x96`; debug slave discovered by `WinComm` is `0x6A`.
- **VCP `0xED` is the USB charging-policy control** on this unit:
  - `ED=0` -> `Charging From NB/PC`
  - `ED=1` -> `No Charging From NB/PC`
- Battery percentage is **not exposed as an ordinary VCP**. A controlled `100% -> 99%` experiment found no VCP matching SOC.
- VCP `0xE3` is **not battery percentage**; it is a 5-step ASUS control (`0,25,50,75,100`).
- VCP power `D6=4` removes the monitor logically and makes Windows reconfigure/flicker. It is unsuitable for a topology-stable black screen.
- A topology-stable black screen is achieved with a borderless topmost black overlay on the MB16AMT plus VCP brightness `0`, restoring brightness afterward.

## Firmware package fingerprints

Official package used during RE:

```text
ASUS_MB16AMT_FW.zip
size:   10,487,921 bytes
SHA256: 8c070d21a9ff95ab9916941fc77c41e913c727d92ac891dca2e26662e18e71dc
```

Extracted firmware image:

```text
ASUS_RL6492_MB16AMT_Project_AUO_B156HAK02_FF000_20211227_V020_4D38_ELot5_reduce.bin
size:   917,504 bytes
SHA256: 1e75681279bf974d2810e6d2ed91aabbeda35de3fabe1881733aa8a12319cb0c
```

The proprietary ASUS package/binaries are **not redistributed in this repository**. See [docs/FIRMWARE.md](docs/FIRMWARE.md) for the extracted layout, hashes, updater settings, and static-analysis notes.

## Repository map

- `HANDOFF.md` — exact current state, what is proven, what failed, what to do next.
- `docs/FINDINGS.md` — consolidated technical findings.
- `docs/PROTOCOLS.md` — DDC/CI, VCP, WinComm, Realtek/ASUS protocol notes.
- `docs/FIRMWARE.md` — firmware package, bank layout, updater/plugin details.
- `docs/DEAD_ENDS.md` — tested paths that should **not** be repeated blindly.
- `docs/EXPERIMENTS.md` — key controlled experiments and observed outputs.
- `docs/SOURCES.md` — public source-code references and provenance notes.
- `NEXT_STEPS.md` — prioritized RE plan.

## Safety status

So far the RE work intentionally avoided destructive firmware operations. No experimental chip erase, flash write, bank erase, arbitrary ISP write, or modified-firmware flash was performed.

Known writes used during probing were limited to normal DDC/CI controls and specific commands observed in ASUS/Realtek code paths. Future work should continue to prefer read-only primitives until a reliable firmware dump + recovery path is established.

## Immediate target

Find the **actual battery SOC data path used by the OSD**. The OSD clearly knows the percentage, but that value has not yet been exposed through MCCS/VCP, generic external I2C probing, `ReadMcuReg`, or the attempted Realtek debug switch.

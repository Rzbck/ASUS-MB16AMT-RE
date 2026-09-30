# ASUS MB16AMT reverse engineering

Reverse-engineering notes for the **ASUS ZenScreen Touch MB16AMT** (Realtek **RL6492** scaler), with a current focus on:

- reading the internal battery state-of-charge from Windows;
- controlling the monitor's USB charging policy without disrupting display topology;
- documenting the ASUS/Realtek firmware-update and DDC/CI paths;
- keeping future firmware work reproducible and safe.

> Start with **[HANDOFF.md](HANDOFF.md)**. It is the canonical state for the next session / next agent.

## Live battery source reader

The ASUS-specific **GET FE/EF/F0** proxy now reads the monitor's internal battery source without entering ISP/debug mode. Run in an elevated PowerShell with the official updater DLLs under `%TEMP%\MB16AMT_RE\fw`:

```powershell
.\tools\Run-SocReadBench.ps1 -Run -BatteryProxy
```

Two independent runs returned source words **6742/6742**, giving **100%** through the exact firmware conversion. The output labels this `raw_target_percent`: the OSD applies a further stateful filter in DA4C, which has not yet been read directly. See [protocol, safeguards and evidence](docs/BATTERY_LIVE_PROXY.md).

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
- Static mapping confirms 14 distinct 64 KiB banks with a repeated 8051-style vector/trampoline prefix; see `docs/STATIC_MAP.md`.
- Public RL6492 source confirms a `Pbank_switch` architecture using XDATA registers `0xFFFC..0xFFFF`, now being correlated against the ASUS image.
- The strong numeric renderer at `1:EAEB` is generic OSD number rendering, but all three known callers are now explained without battery SOC. `DA86` is a one-second OSD countdown; see `docs/DA86_TIMER.md`.

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

## Reproducible local analysis

The verified firmware remains local. Run the full read-only suite with:

```powershell
python tools/run_offline_suite.py "C:\path\to\V020.bin" --out work\suite
```

For a faster pass that skips the exhaustive `8:5FEF` emulation:

```powershell
python tools/run_offline_suite.py "C:\path\to\V020.bin" --out work\suite --quick
```

The suite verifies the exact V020 size/SHA before running anything. It includes:

- banked ABI / CFG reconstruction;
- generic numeric-renderer verification;
- decoded **VCP `ED` dispatcher-candidate analysis**;
- setting-query provenance/emulation unless `--quick` is used;
- the PowerShell bank/vector and bank-switch mappers when `pwsh` is available.

All generated output stays under `work/`, which is ignored by Git.

## GitHub Actions

`.github/workflows/public-repo-ci.yml` runs on pushes and pull requests. It deliberately does **not** contain or download the proprietary firmware. It checks:

- obvious personal/device-unique identifiers and common secret formats;
- accidental tracked firmware/updater binaries and dumps;
- Python syntax/import/CLI regressions;
- PowerShell parser errors.

`tools/check_public_repo.py` is the corresponding local/CI privacy guard. It scans the current tracked tree; it does **not** rewrite or purge old Git history.

## Repository map

- `HANDOFF.md` — exact current state, what is proven, what failed, what to do next.
- `docs/FINDINGS.md` — consolidated technical findings.
- `docs/PROTOCOLS.md` — DDC/CI, VCP, WinComm, Realtek/ASUS protocol notes.
- `docs/FIRMWARE.md` — firmware package, bank layout, updater/plugin details.
- `docs/STATIC_MAP.md` — incremental 8051/banked firmware map, bank fingerprints, vector evidence, and bank-switch correlation.
- `docs/DA86_TIMER.md` — confirmed one-second DA86 OSD countdown path and SOC consequence.
- `docs/DEAD_ENDS.md` — tested paths that should **not** be repeated blindly.
- `docs/EXPERIMENTS.md` — key controlled experiments and observed outputs.
- `docs/SOURCES.md` — public source-code references and provenance notes.
- `tools/run_offline_suite.py` — one-command local V020 analysis entrypoint.
- `tools/analyze_vcp_dispatch.py` — decoded VCP `ED` / vendor-literal dispatcher candidate finder.
- `tools/Analyze-FirmwareMap.ps1` — read-only local V020 bank/vector mapper with image hash validation.
- `NEXT_STEPS.md` — prioritized RE plan.

## Safety status

So far the RE work intentionally avoided destructive firmware operations. No experimental chip erase, flash write, bank erase, arbitrary ISP write, or modified-firmware flash was performed.

Known writes used during probing were limited to normal DDC/CI controls and specific commands observed in ASUS/Realtek code paths. Future work should continue to prefer read-only primitives until a reliable firmware dump + recovery path is established.

## Immediate target

Find the **actual battery SOC data path used by the OSD**. The active static strategy is now:

1. locate and confirm the ASUS handler for the runtime-proven VCP `0xED` charge policy;
2. trace its internal power/charging callees and cached state;
3. locate the alternative numeric/glyph path used by the battery OSD, since `1:EAEB`'s known callers are now non-SOC;
4. derive the battery acquisition primitive before attempting any new runtime probe.

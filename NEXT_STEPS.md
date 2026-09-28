# Next steps — prioritized

The project has enough negative runtime evidence that the next session should **not** begin with another blind probe. Start from static analysis.

## P0 — Build a usable static map of the ASUS V020 image

**ABI milestone completed 2026-09-28:** 741 thunks resolved, old-bank return
mechanism checked, all 27 non-table FFFF occurrences classified. See
`docs/STATIC_MAP.md` and `docs/maps/`. Do not restart the old selector search.
The partial graph has 2,540 decoded thunk-transfer sites; it does not yet resolve
all indirect dispatch or all function boundaries. The next active priority is P1.

Target:

```text
ASUS_RL6492_MB16AMT_Project_AUO_B156HAK02_FF000_20211227_V020_4D38_ELot5_reduce.bin
SHA256 1e75681279bf974d2810e6d2ed91aabbeda35de3fabe1881733aa8a12319cb0c
```

Tasks:

1. DONE: document the `0xE0000` image as 14 x `0x10000` banks;
2. DONE for the common call ABI: verify selectors, gates, thunks and stack return;
3. use separate physical-bank:local and logical-bank:local identifiers; keep boot/partition identity provisional;
4. identify common Realtek library functions by matching instruction/constant patterns against public RL6492 source;
5. produce a symbol notebook/map even if function names are initially inferred.

Deliverable: `docs/STATIC_MAP.md` with bank map + candidate functions.

## P1 — Trace battery percentage from the OSD backward

**8:5FEF contract DONE:** see `SETTING_QUERY.md`; it is a query of stored settings,
not hardware acquisition.

**DA86 path DONE:** see `docs/DA86_TIMER.md`; `DA86` is decremented by user timer
event `0x17`, displayed once per event through `4:F058 -> 1:EAEB`, and followed
by zero/completion cleanup. It is a countdown path, not a SOC path.

**Important pivot:** all three known raw callers of numeric renderer `1:EAEB`
are now explained by non-battery UI:

1. `10:C41E` — generic setting display via `8:5FEF`;
2. `10:E9F7` — generic setting UI scratch via `D82E:D82F`;
3. `4:F058` — `DA86` one-second countdown.

Therefore do **not** keep treating `1:EAEB` / public `OsdPropShowNumber` as the
battery renderer merely because it handles decimal values. The battery OSD is
likely using another numeric/digit/string path.

The OSD remains the ground truth: it can display exact values such as 74, 73,
99 and 100.

### Active P1 tasks

1. Identify the compiled DDC/VCP handler for **confirmed VCP `0xED`** and trace
   its read/set branches into charging and power-management state.
2. From that power-management graph, identify cached battery/charge fields and
   trace their writers back toward I2C/ADC/PMIC/gauge acquisition.
3. Independently enumerate alternate numeric/digit rendering paths used by OSD
   code (direct digit glyph construction, small fixed-width number renderers,
   percent-specific helpers, battery-status strings/icons).
4. Search those alternate renderers for callers whose value is naturally 0..100
   and whose surrounding logic intersects power/charge state.
5. Resolve indirect dispatch only where it blocks these concrete paths.

Look for:

- comparison thresholds near 20 and 100;
- periodic battery/charge refresh events;
- branches tied to charge policy represented externally by VCP `ED`;
- cached power fields updated outside generic OSD setting code;
- I2C/ADC/PMIC primitives reached from those writers.

Do not search only for the ASCII word `battery`; there are no useful plain-text
battery strings in the image.

## P2 — Recover the ASUS board's actual power/battery device

Once a battery-related code path is found, derive from firmware rather than guessing:

- I2C slave address;
- bus/channel;
- register numbers;
- read length/endian format;
- voltage/current/SOC conversion;
- charge-enable GPIO/PMIC action;
- whether SOC is direct from a gauge or computed from voltage/ADC.

Cross-reference with RL6492 public source only after extracting constants from the ASUS image.

Stop condition: do not ask the user to probe a new address until the firmware gives a concrete reason for that address/register.

## P3 — Understand why debug/signature mode is unavailable at runtime

Known state:

- normal `0x6E` works;
- expected signature handshake returns DDC NULL;
- direct `77 55` does not activate `0x6A`;
- `0x6A` remains unavailable.

Investigate statically:

1. whether ASUS V020 compiled signature/debug handlers out, gates them behind a state flag, or routes them through another channel;
2. whether the updater first performs a prerequisite command/reset/power-cycle before the signature handshake;
3. exact call chain inside `WinIspPlugIn.dll` leading to mode detection / mode switching;
4. whether `enumDigitalSignatureType=1`, `enumSWDigitalSignatureMode=4`, and `enumIspMode=1` select a different updater flow than the public Realtek example.

Do not brute-force `77 xx` opcodes.

## P4 — Find a safe read/dump primitive in ASUS tooling

`WinIspPlugIn.dll` exports `DumpFlash`, but the plugin requires updater context pointers.

Goal: reconstruct only the minimum safe initialization needed for a read-only dump.

Tasks:

- map the interface table consumed by `SetCommInterface`;
- identify which callbacks `DumpFlash` actually dereferences;
- map `SetIDev` / `SetUIFunction` requirements;
- determine whether DumpFlash enters ISP/reset mode and whether that is reversible without a write;
- compare dumped bytes against the known V020 package before trusting the primitive.

Do not invoke `ChipEraseFlash` or `IspFlash`.

## P5 — Preserve the proven useful controls

Turn known-good discoveries into small utilities later:

- read/set VCP `ED` charge policy;
- topology-stable black screen overlay + brightness restore;
- safe VCP inventory/snapshot.

These utilities should be separate from experimental firmware probes.

## P6 — Low-priority paths only if static RE stalls

- observe behavior below 20% SOC because ASUS ECO behavior may introduce additional PC communication;
- inspect DisplayLink/ASUS user-mode traffic if a driver/service is found to receive battery events;
- investigate touch/vendor HID only if firmware or USB descriptors connect it to power management.

## Rules for the next runtime experiment

Every new experiment should state before execution:

1. exact hypothesis;
2. exact source evidence supporting it;
3. expected positive result;
4. expected negative result;
5. restore/recovery path;
6. why the same question was not already answered by a previous test.

This should prevent another loop of generic scans and repeated handshakes.

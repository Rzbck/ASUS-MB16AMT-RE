# Battery percentage: source to OSD (V020)

Verified 2026-09-30 against the SHA256-pinned V020 image. Addresses use the existing bank mapping; physical partition identity is still provisional. This is a static proof, not a live percentage measurement.

## Confirmed chain

```text
GPIO I2C P5.6/P5.7, slave 0x55 (8-bit AA/AB), subaddress 0x10, four bytes
 -> 0:681E -> 0:6D00 read into D829..D82C
 -> 0:5A5C: two LE16 words u,v; x=(u*10000//v)&FFFF
 -> piecewise conversion, R7=0..100 or FF invalid
 -> 0:6EB9: filter using DCC2 and DCC1
 -> 9:E79E..E7A2: DA4C=current displayed percentage (DA4D=previous)
 -> 10:AAA0 / 10:F6A4: DA4C passed in R3
 -> 10:F8F4: decimal glyphs D837, pointer 01 D8 37 at DCC6..DCC8
 -> string selector 3A -> thunk 1922 -> 1:D7A1
```

The battery renderer is different from `1:EAEB`. The old setting-query and countdown exclusions remain valid.

## Independent battery semantics

The encoded string at `1:A0EF` decodes to `Out of battery soon!`. Selector 30 reaches `1:E76D` and builds its generic code pointer. The bounded dispatch at `10:D862` selects `10:D8F4` for warning type 7, drawing selectors 30 and 31. `9:9D82..9DA3` selects type 7 when DA4C=1, type 6 when DA4C is 2..5. This links the same numeric field to a battery-specific warning independently of a coincidental value of 100.

## Acquisition and conversion

`0:681E` supplies R7=AA, R5=1, R2:R3=0010, length=4 and output pointer 01:D829. `0:6D00` sends the subaddress through `0:FBDF`, then the read address AB, receives four bytes, ACKs intermediate bytes, NACKs the last and stops. `0:6F1E` bit-bangs FE0E/FE0F. The public RL6492 register header names these P5.6/P5.7. This is an internal software I2C path, not an ADC conversion.

A zero denominator returns FF. A failed transaction is retried once; after two failures the firmware sets DA51.bit0 and toggles P3.5 with delays. The offline verifier mocks I2C and never executes those effects on hardware.

The ratio x is stored in D82D:D82E. Integer rounding is part of the behavior:

| x | Returned R7 |
|---|---|
| 0..549 | 0 |
| 550..2949 | (((x-550)*29//24)+100)//100 |
| 2950..8049 | (((x-2950)*56//51)+2999)//100 |
| 8050..9449 | (x+550)//100 |
| 9450..10000 | 100 |
| 10001..65535 | FF (invalid) |

Thus the unfiltered displayed target reaches 100 at a raw ratio of 94.50%. A direct gauge SOC read would not necessarily equal this display.

## Filter, cache and writers

`0:6EB9` holds the current target in DCC2 and countdown in DCC1. If DCC2=FF it initializes from a valid raw value, or 50 on invalid input. Invalid input subsequently holds the cache. Equal input clears the countdown. Different valid input decrements a nonzero countdown and holds the value; at zero it moves one percentage point toward the input and reloads 12. This is one step every 13 differing valid invocations; the wall-clock period remains unproven.

`9:E77F` decrements DA58 until zero, then calls acquisition (1A7E) and filter (1A84). It accepts R7<=100, copies old DA4C to DA4D and writes DA4C. Other manually checked direct writers initialize DA4C/DA4D to 80 at `4:F35D..F364`, or restore D9F7 to DA4C and DCC2 at `4:F42C..F437`. This inventory does not exclude indirect writers. A runtime read must account for startup/restored values and failed acquisition.

`10:F8F4` accepts R7=row, R5=column, R3=value. Decimal digit n is glyph n+1, followed by FF. All 101 values were verified. A diagnostic branch at `10:F6CD` calls raw acquisition directly; ordinary display callers use filtered DA4C.

## Verification

`tools/trace_battery_provenance.py` executes original instructions in the existing bounded MCS-51 interpreter: 65,536 curve inputs, 36 mocked acquisition scenarios, 2,754 filter cases and 101 rendered percentages. See `maps/battery-provenance.json`. Hardware input is explicitly mocked, and execution stops before the hardware-facing string renderer.

The CFG now recognizes guarded adjacent LJMP tables, including the warning and numeric display dispatches: 158,425 instruction starts, 2,986 thunk edges, 20 unresolved indirect jumps, no decoded overlaps or reserved opcodes. CSV selector_index is the guarded A index; at 4:EC36 this is R7-1.

## Live result and remaining uncertainty

On 2026-09-29 at 18:15:23Z, six valid DDC control responses preceded one firmware-derived `I2CReadEx(AA,10,4,buffer,1)` through backend 6. It returned 0x2B0A after 500 ms, unchanged A5 sentinel bytes, intact guards. No valid source data or live percentage was obtained. `Run-SocReadBench.ps1 -Run -BatterySource` reproduces that bounded probe. It is not a working SOC reader. The external bridge has not been shown to reach the internal GPIO bus.

The user's latest OSD observation was 100%; it is not a measurement made by these tools. Exact fuel-gauge model and the physical units of u/v remain unproven. Their address and ratio are consistent with capacity words, but do not identify a particular chip.

Next: trace D9F7 cache provenance and existing read-only protocol routes to DA4C or the internal I2C bus. Do not treat scaler register reads as XDATA access, repeat address sweeps, or invoke firmware routines that toggle pins.

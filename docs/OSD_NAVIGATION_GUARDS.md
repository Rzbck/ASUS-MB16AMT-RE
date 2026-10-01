# Navigation mode, command and timer guards

CONFIRMED bounded instruction contracts in bank9, using the pinned V020 image.
The [verifier](../tools/map_osd_navigation_guards.py) and
[report](maps/osd-navigation-guards.json) execute404,224 offline fixtures.
These are connected blocks, not a claim that the entire navigation entry or
every setting/mode combination is proved.

## Command threshold and mode routing: A16F..A1D1

**1532 ->7:FED0 ->7:E873 returns DCB7&1F in R7.** Mode numbers below are
that masked field; physical/system labels remain unassigned.

A16F sets scratch **D820=6 if DA68 bit1 is set, otherwise5**.
AB44 returns carry iff unsigned DA6D<D820, with A=DA6D-D820 modulo256.
All65,536 command/threshold byte pairs verify this comparison.

Routing then evaluates:

| Condition, in order | Boundary |
|---|---|
| Mode5, DC77 nonzero, command<threshold, DA6B!=5 | A384 RET |
| Otherwise command<threshold and mode3 | A1D1 overlay-release block |
| Otherwise command<threshold, mode5 or8, DA6B=5 | A1D1 overlay-release block |
| Every other checked combination | A334 fallback |

131,072 fixtures cover all32 masked modes/all256 commands, DA6B=00/05/56/58,
DA68=00/02 and DC77=0/1. Another8,192 fixtures cover all raw DCB7 bytes,
commands0..7, settings0/5 and both threshold flags. Only D820 is written
before those boundaries. This connects [input command publication](OSD_COMMANDS.md)
to the [overlay release/dispatch gates](OSD_OVERLAY_GATE.md).

## Conditional timer request: A129..A16C

The block requests **0B7E ->5:E77F** only when all are true:

- DCB7&1F equals1,5 or6;
- DA4E bit4 is clear;
- FE0B equals0;
- DA92 bit2 is set.

Arguments are **R5=16h** and **R6:R7=(BE16 DA5E:DA5F+500) mod65536**.
All65,536 source words verify addition including carry/wrap. There are2,816
gate fixtures: all raw DCB7 bytes with representative flag combinations,
then every DA4E/FE0B/DA92 byte separately under otherwise eligible conditions.
The verifier stops before the scheduler.500 is an argument increment, not
a measured delay, and no clock/interrupt behavior is emulated. Rejected cases
continue to the next D820 threshold write, where this check stops.

## Normal-path special transition: A21F..A23E

AB99 extracts DA00 bit2. The following two-iteration rotate normalizes it.
If that bit is set and DA6B=0, the code calls **19A0 ->12:FEFB**, which returns
direct RAM bit1C as carry. If carry is clear, **R7=5D; LJMP1640 ->10:AD44**.
Otherwise it reaches the normal callback selector9:A23E.

All131,072 DA6B/DA00/bit1C combinations verify the exact condition and no
XDATA write before either boundary. This follows the DA68 bit1 alternate
dispatch choice atA212; see [OSD_HANDLERS.md](OSD_HANDLERS.md).
DA00 bit2 and bit1C physical meanings remain unassigned. No assumption is
made that state5D is a particular visible screen.

Next precise targets: **9:A334..A384 fallback**, its modes4/6, command guard,
timer cancellation/scheduling, then the preceding navigation entry and
DA6E command/repeat flag lifecycle. Native glyph identities and other
settings/windows remain separate open portions of the full OSD map.

```powershell
uv run --locked --offline python tools/map_osd_navigation_guards.py $fw --out docs/maps/osd-navigation-guards.json
```

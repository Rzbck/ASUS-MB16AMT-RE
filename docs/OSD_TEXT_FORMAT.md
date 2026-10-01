# OSD text pointers, segments and font prefixes

Verified against the repository's SHA-pinned V020 image using bounded offline
execution. Static bank-model qualifications from [OSD_ATLAS.md](OSD_ATLAS.md)
apply. No hardware execution or firmware patch was performed.

## Segment traversal

The string renderer `1:D7A1` obtains the resolved generic pointer and stores it
in `D861..D863`. At `D7D1..D7D5` it copies `D842` into direct RAM `26h`.
The loop at `D7D7..D7EF` scans bytes through the generic-pointer read helper:

1. If count=0, continue at D7F1 immediately.
2. Read the byte at the current pointer.
3. Decrement count only for byte FF.
4. Increment the 16-bit pointer, including low-byte carry, and repeat.

Thus the selected text begins immediately after the last skipped FF. The
pointer tag in D861 is preserved; only the address bytes D862/D863 change.
The test stops before rendering, so no peripheral behavior is mocked as a proof.

The independent tests compare actual instruction execution against a simple
segment-length model for 15 synthetic cases: unequal lengths, empty segments,
embedded F8..FE-like bytes, and low-byte/page crossings. Twenty-one further
tests scan the actual code resource at `1:A0EF`; the resulting end address is
exactly `1:A317`, the next resolved resource pointer. This proves the 21
segment boundaries in that interval. It does not prove their language names,
that all are selectable, or that all resources share the same cardinality.

Menu provenance follow-up: `DA03 & 3F` feeds segment counts D855 and D865
in the DC4F/D2D8 text paths, verified through their actual helpers/prologues.
See [OSD_CELL_RENDERER.md](OSD_CELL_RENDERER.md). D842 is the count field in
the D7A1 path; scratch addresses must be interpreted in their routine context.

The public Realtek `OsdPropPutString` routine likewise decrements a language
counter on terminators before rendering. This corroborates the language-index
interpretation of D842. ASUS validation is now checked below; language names
and all caller paths remain to be mapped.

## Stored language range and masked update

The validator at **8:7911..7931** accepts `DA03 & 3F` in **0..20 inclusive**.
Values 21..63 clear direct bit 03h and replace the low six bits with the code
default at `8:40B2` (zero). The upper two bits are preserved. All 256 packed
DA03 inputs were executed to the next-field boundary at 7935. The test leaves
direct bit 03h set for valid values and observes it cleared for invalid ones;
its wider meaning is not assigned by this field-local check.

This matches setting-query selector **32**: mode 0 returns DA03 low six bits;
modes 1/2/3 return 20/0/1. The query was checked in 259 additional cases. The
validated range has 21 indices, matching the independently scanned 21 warning
segments. This establishes the stored index range for this validator, not
language names or a universal 21-segment claim for every resource.

The masked update tail **6:BA79..BA9D** copies `D823 & 3F` into DA03 while
preserving DA03 high bits, then clears DA87.bit3. All **65,536 previous/new
byte pairs** pass. This tail accepts masked values above 20; do not attribute
the validator's range restriction to this tail. The full upstream adjustment
routine, navigation, persistence and validation invocation remain open.

## Prefix classification and width dispatch

The first scan at `1:D803..D825` classifies exactly **F8..FE** as special tokens.
All 256 input-byte cases were checked offline. `1:D0AF` stores a recognized
token in D867 and increments the current byte index in direct RAM 28h.
D866 carries the prefix used for the next glyph lookup. FF remains the segment
terminator; the prefix meaning cannot be copied directly from reference enums.

`1:DC42` passes the glyph byte in R3, D842 in R7, and the saved prefix in R5
to `1:FCE6`. This width dispatcher selects:

| Condition | Width routine |
|---|---|
| Prefix FA, or D842=0E | 11:FD9D |
| D842=0F or 10 | 5:D761 |
| D842=11 or 12 | 2:EB91 |
| D842=13 | 0:629A |

The default/unsupported case must not be treated as a valid width without
following its incoming registers. At `11:FD9D`, the common FA table is read at
`11:F11B + 2*glyph`; its result is clamped to 4..12. For D842=0E, prefixes
FB/FC/FD choose other tables at F2F5/F4D7/F6B9. These are static observations;
full width-table bounds and all other branches remain to be tested.

## Glyph-byte dispatch and hardware boundary

`1:FC2B` receives D842 in R7, prefix in R5, and a byte offset in R2:R3. It
selects generic code pointers in the font banks. The common FA path reaches
`11:FE5F`, whose base is `FF:995A`; its D842=0E extension bases are B23E,
CB8E and E4DE for FB/FC/FD. Separate paths dispatch to banks 5, 2 and 0.

The renderer's `1:DC0E..DC2D` and `1:DC2F..DC36` write returned bytes to
XDATA **FF06**. This is a concrete peripheral boundary for font-byte output.
The setup of that port, glyph allocation, rotation and SRAM layout still need
to be connected before claiming complete rendering semantics.

## Verified common-font output arithmetic

`1:DBCA` calculates `27 * RAM[29h] + 3 * RAM[26h]`: glyph code
and triplet index respectively. It calls `1:FC2B` three times with consecutive
offsets and writes the three returned bytes chronologically to **FF06**.
For D842=0E, FA/FB/FC/FD select bank-11 bases 995A/B23E/CB8E/E4DE.
The guard at `1:D11D` increments RAM[26h] and returns carry when the resulting
byte is below 9; the renderer repeats at `1:DAB6` while that condition holds.
A full cell starting at index zero therefore transfers **27 bytes**.

`tools/map_osd_font.py` executes the actual instructions and independently
checks 256 common-width inputs, 2,340 three-byte transfers and all 256 guard
inputs. Common widths exactly equal `clamp(code[11:F11B + 2*glyph], 4, 12)`.
The output checks cover FA codes 00..EB and eight codes for each of FB/FC/FD,
with all nine triplets. Tested code ranges are mechanical coverage, not proof
of legal glyph enum bounds. No bitmap bytes are exported.

The checks record peripheral writes in memory. They do not establish pixel
dimensions, packing, compression, rotation, timing or real SRAM configuration.
The following section verifies the remaining dispatched font banks. Full
glyph bounds still need verification.
See [derived output contract](maps/osd-font-output.json).

```powershell
uv run --locked --offline python tools/map_osd_font.py <local-V020.bin> --out docs/maps/osd-font-output.json
```

## Remaining font banks: verified dispatch

The extended `map_osd_font.py` checks **37,632 width cases**: all 21 stored
language indices, all seven F8..FE prefixes and all 256 glyph bytes. It also
checks **3,096 triplet outputs** from the actual DBCA renderer: the shared FA
path for every language index and all 22 mapped extension tables, with eight
glyph inputs and all nine triplets each. These supplement the common-cell
checks above. All independent width/byte formulas match instruction execution.

FA always selects width table 11:F11B and font base 11:995A, regardless of
language index. Extension tables are:

| Index (hex) | Prefix | Width base | Font base | Width index |
|---|---|---|---|---|
| 0E | FB | 11:F2F5 | 11:B23E | 2*glyph |
| 0E | FC | 11:F4D7 | 11:CB8E | 2*glyph |
| 0E | FD | 11:F6B9 | 11:E4DE | (2*glyph)&FF |
| 0F | FB | 5:A487 | 5:2DC4 | 2*glyph |
| 0F | FC | 5:A669 | 5:4714 | 2*glyph |
| 0F | FD | 5:A84B | 5:6064 | (2*glyph)&FF |
| 10 | FB | 5:A929 | 5:6BFE | 2*glyph |
| 10 | FC | 5:AB0B | 5:854E | 2*glyph |
| 10 | FD | 5:ACED | 5:9E9E | (2*glyph)&FF |
| 11 | FB | 2:C8CF | 2:2DC4 | 2*glyph |
| 11 | FC | 2:CAB1 | 2:4714 | 2*glyph |
| 12 | FB | 2:CC87 | 2:5FC2 | 2*glyph |
| 12 | FC | 2:CE5F | 2:788B | 2*glyph |
| 12 | FD | 2:D051 | 2:92B3 | 2*glyph |
| 12 | FE | 2:D231 | 2:ABE8 | 2*glyph |
| 12 | F9 | 2:D387 | 2:BDD6 | (2*glyph)&FF |
| 13 | FB | 0:F0AF | 0:7002 | 2*glyph |
| 13 | FC | 0:F293 | 0:896D | 2*glyph |
| 13 | FD | 0:F475 | 0:A2BD | 2*glyph |
| 13 | FE | 0:F65F | 0:BC79 | 2*glyph |
| 13 | F9 | 0:F825 | 0:D44F | 2*glyph |
| 13 | F8 | 0:FA01 | 0:EE77 | (2*glyph)&FF |

Width-table values are clamped to 4..12. Narrow indexing uses byte doubling
and discards glyph bit 7; codes separated by 80h alias the width lookup. The
font-byte offset still uses `27*glyph + 3*triplet`. This is an important edit
constraint, but it does not establish legal glyph-code bounds.

For non-FA prefixes without a matching table, indices 0E..13 return width 12.
Indices 00..0D and 14 instead return the untouched incoming language byte in
R7 from the width dispatcher. These are mechanical fallback results, not valid
glyph widths or proof that those token combinations occur in real text.
The font-byte tests cover mapped tables only; unsupported pointer paths are
not asserted valid. Language names, full cell/pixel encoding and setup remain
open.

## Consequences for future edits

- Text is a glyph/token stream. An ordinary ASCII replacement is not an
  equivalent resource.
- Segment FF delimiters and prefix state are part of the format. A prefix edit
  can select a different font table rather than simply change punctuation.
- A resource-length change affects later segments and potentially later
  resource bases. The pointer resolver, bounds and layout widths must agree.
- M/W fragments in the current index are still candidate transcriptions.
  Validate their bitmap/width pairing before normalizing them to single letters.
- Stored language validation is established; names, all selection callers and
  font limits remain open.
  No ready-to-flash patch is established by this document.

## Reproduce

```powershell
uv run --locked --offline python tools/map_osd_text.py <local-V020.bin> --out docs/maps/osd-text-format.json
```

[Derived checks and segment boundaries](maps/osd-text-format.json) contain no
firmware bytes or font bitmaps. Next: verify all width/font dispatch branches,
then language adjustment/persistence and key/state transitions.

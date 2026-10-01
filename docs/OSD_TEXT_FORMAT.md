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

The public Realtek `OsdPropPutString` routine likewise decrements a language
counter on terminators before rendering. This corroborates the language-index
interpretation of D842; its ASUS enum and validation remain to be mapped.

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
The remaining language banks and full glyph bounds still need verification.
See [derived output contract](maps/osd-font-output.json).

```powershell
uv run --locked --offline python tools/map_osd_font.py <local-V020.bin> --out docs/maps/osd-font-output.json
```

## Consequences for future edits

- Text is a glyph/token stream. An ordinary ASCII replacement is not an
  equivalent resource.
- Segment FF delimiters and prefix state are part of the format. A prefix edit
  can select a different font table rather than simply change punctuation.
- A resource-length change affects later segments and potentially later
  resource bases. The pointer resolver, bounds and layout widths must agree.
- M/W fragments in the current index are still candidate transcriptions.
  Validate their bitmap/width pairing before normalizing them to single letters.
- Exact language selection, supported indices and font limits remain open.
  No ready-to-flash patch is established by this document.

## Reproduce

```powershell
uv run --locked --offline python tools/map_osd_text.py <local-V020.bin> --out docs/maps/osd-text-format.json
```

[Derived checks and segment boundaries](maps/osd-text-format.json) contain no
firmware bytes or font bitmaps. Next: verify all width/font dispatch branches,
then identify the menu's language validator and key/state transitions.

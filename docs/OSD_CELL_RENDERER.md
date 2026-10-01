# OSD cell resources, drawing port and menu parameter provenance

Verified offline against the SHA-pinned V020 image, using the existing bounded
8051 interpreter and bank ABI. No monitor command or firmware patch is involved.
Static bank-model limits from [OSD_ATLAS.md](OSD_ATLAS.md) apply.

## Two resource formats

`1:E43B` resolves multilingual text. **`1:EEED` is a separate resolver** used
by `1:F7B2` for cell streams. EEED accepts R7 selector and R5 index, returning
the generic pointer in R3:R2:R1 and D840..D842. All 256 selectors with indices
0/1 were compared against independently transcribed fixed/table rules (512
checks); writes are confined to the three pointer scratch bytes.

| Selector | Indexed pointer table, bank 1 |
|---|---|
| 3F | C66F |
| 44 | C773 |
| 45 | C9F9 |
| 46 | C919 |
| 48 | CA3D |
| 4A | CA88 |
| 5C | C699 |

Indexed addresses are `table + 3*R5`; the loaded triple is a generic pointer.
Fixed code resources are 47→CA05, 49→CA40, 4C..59→C6A2..C6BC (step two),
5A→C6BF and 5B→C6C2. Other byte selectors return the cleared zero pointer in
the tested cases. The input range is checked after byte subtraction of 3F;
this is not a test of legal caller index bounds or resource visual identity.

## Cell-stream consumer

`1:F7B2` stores R7 into D833 (row) and R5 into D834 (initial column), then
passes **R3 as the resource selector** and **D836 as its index** to EEED.
The returned pointer is copied to D83B..D83D. D83A tracks the current column;
D837 supplies color; D838 caches the chosen stride (DC09 for row<100, DBFC
otherwise). These parameters are distinct from text-renderer scratch fields.

Execution at `1:F7E7` establishes the following format:

| Token | Operation |
|---|---|
| Ordinary byte | Draw that glyph, then increment current column |
| FE | Increment row and reset column to D834 |
| FD, count | Emit the byte immediately before FD another count−1 times; consume these two bytes |
| FF | Return without drawing the terminator |

After each glyph, column equality with D838 triggers a row advance/reset,
unless the next byte is FE. Inside the FD repeat loop that comparison reads
the count byte, so count=FE suppresses automatic wrapping. This corner case
is verified mechanically; its use in real resources is not established.
FD count zero, malformed streams and legal stream lengths remain open.

120 synthetic RAM fixtures check actual firmware execution through the complete
drawing leaf, including empty streams, consecutive FE, six repeat counts,
automatic wrapping, the row-100 boundary and row-byte wrap. Fixtures enter
after pointer resolution; no patched firmware or exported bitmap is used.

## Exact cell drawing boundary

`8:D83D` accepts R7 row, R5 column, R3 glyph and D841 color. Its path is:

```text
1:F87C -> thunk 1AA8 -> 8:D83D
       -> thunk 1B50 -> 6:F851
       -> thunk 0EBA -> 8:EE13
       -> thunk 1C28 -> 13:6137
```

Address arithmetic, modulo 65536:

```text
row < 100: BE16(X[DC04..DC05]) + X[DC09] * row + column
otherwise: BE16(X[DBF9..DBFA]) + X[DBFC] * (row - 100) + column
```

The leaf writes control `0094 = (old & 13h) | E8h`, preserves bit 7 of 0090
while replacing its low seven bits with the masked address high byte, and
writes the address low byte to 0091. The chronological **0092 payload** is:

```text
C0, glyph, (color & 3) * 55h
```

768 checks cover every row byte with three different column/glyph/color
combinations and distinct bases/strides. Register writes are recorded in memory;
this proves instruction-level byte/address behavior, not visible screen
coordinates or peripheral timing. The 0092 cell path and FF06 font-byte path
must be mapped together with initialization to complete SRAM semantics.

## Menu category and language sources

At `10:B03E`, the existing getter is called with R7=0C/R5=0. It returns
`DA0A & 0F`, stored into **D823 at B048**. All 256 packed source bytes were
checked. `10:B0A1` then selects the nine-entry table at B0B4:

| D823 | Handler |
|---|---|
| 0 | 10:B0CF |
| 1 | 10:B16B |
| 2 | 10:B1D1 |
| 3 | 10:B217 |
| 4 | 10:B265 |
| 5 | 10:B2CA |
| 6 | 10:B37F |
| 7 | 10:B411 |
| 8 | 10:B440 |

All byte inputs were executed to the handler boundary. Values>=9 go to B572.
Handler names, navigation and key events are not assigned by this table test.
D823 is reused as an iteration counter inside handlers; do not rename it to
a permanent menu-state variable.

The text language/segment index comes from **`DA03 & 3F` at 10:B617**.
`10:B613` writes family/index to the incoming DPTR and *falls through B617*;
it returns that masked language in A. Two proven caller chains are:

```text
B613 -> BA0A -> D855 -> 1:DC4F (reads count at DC87)
B613 -> BE58 -> D865 -> 1:D2D8 (reads count at D30F)
```

1,536 checks execute the helpers and renderer prologues for all 256 packed
DA03 values, family-03 indices 0/1/4, and both paths, stopping before segment
traversal. This establishes menu-text provenance. It does not establish that
all 64 masked indices are legal languages; the setter/validator remains open.

## Reproduce and remaining targets

```powershell
uv run --locked --offline python tools/map_osd_cells.py <local-V020.bin> --out docs/maps/osd-cell-renderer.json
```

[Derived contract](maps/osd-cell-renderer.json) exports addresses and checks,
without proprietary resource bytes. Next: DA03 language validation; category
handler labels/setting selectors; key navigation; DC04/DBF9 bases and DC09/DBFC
stride initialization; font/cell connection, palette and persistence.

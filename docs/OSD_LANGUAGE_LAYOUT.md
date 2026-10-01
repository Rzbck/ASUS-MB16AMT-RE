# Language-menu entry contracts and selection geometry

This extends [preview/apply/save provenance](OSD_LANGUAGE_UPDATE.md) with
bounded entry and refresh contracts on the pinned V020 image. These are
separate executed subpaths, not a claim of full menu initialization emulation.
All MOVX effects occur in offline memory; no hardware command is sent.

## Confirmed entry and staged-value seed

The normal DA6B row32 command0 cell points to **9:F550**. Its pre-drawing
call19E8 receives R3=4, R7=28h and R5=2. The later F569..F56B instructions
pass **R7=56h** to `19EE -> 10:D370`. The F578..F582 tail seeds
**DA48:DA49=00:(DA03&3F)** through A9B5. These caller/seed checks cover all256
packed DA03 values with DA83=0/7 (512 fixtures); the drawing calls between
the checked boundaries remain excluded.

The actual D370 prologue saves R7 to D824, clears direct bit03 and
**D825..D82D**, then sets **DA68.bit6 iff previous DA6B equals the target**,
otherwise clears it. All65,536 previous-setting/flag combinations pass for
target56. The old DA6B is retained at this boundary.

The subsequent actual target56 guards reach D64B's F85D drawing call when
entering from row32 (R7=1A, direct bit04=1). Re-entering row56 instead returns
at D686 without this drawing call. All256 DA68 inputs, both previous rows
and both incoming carries pass (1,024 fixtures).

Later within the new-row drawing branch, **D735** loads R5=D824 and R7=1,
then calls **BE8C**. The actual BE8C..BEA4 prefix writes:

| State | Result for target56 |
|---|---|
| DA6B | 56h |
| D82E | 01h |
| D82F | Previous DA6B |
| D830..D832 | Zero |

All256 previous settings and both carries pass (512 fixtures). Two separate
row32 fixtures continue to **C436 -> EBCD**, with R7=10h, before more drawing.
The captured D82E..D832 values are transition scratch at this boundary;
these bytes have other previously verified uses and must not be globally
renamed as a single permanent history structure.

## Confirmed geometry before the refresh drawing call

The preview callback passes selected index in R5 to **19DC -> 10:CA2A**.
CA2A stores selector/value in D833/D834. With DA70.bit0 clear, its row56
branch reaches **CD7E..CEC6**, which computes the following four BE16 fields:

| Index | Local index n | D83C | D83E | D840 | D842 |
|---|---:|---:|---:|---:|---:|
| 0..7 | index | 300 | 72+36n | 455 | 108+36n |
| 8..15 | index-8 | 456 | 72+36n | 611 | 108+36n |
| 16..20 | index-16 | 612 | 72+36n | 780 | 108+36n |

The third group omits the minus1 used by the first two; it must not be
normalized to779. D834 becomes the local index; D836 is19h/26h/33h;
D837 is0Dh/0Dh/0Eh. The tail also sets D844:D845=00:07 and direct bit05=1,
then calls **F142 with R7=6**.

**168 fixtures** execute this arithmetic block: all21 indices, both incoming
carries and four initial XDATA fill patterns. Assertions cover all four fields,
scratch writes, configuration bytes, direct bit05 and balanced explicit stacks.
They begin at CD7E and stop before F142; CA2A's earlier drawing calls and
DA70.bit0 alternate path are excluded.

The fields' role as a selection/highlight rectangle is **strong evidence**.
Language names are not assigned from index order alone.

## Confirmed window packing and register-transfer preparation

An additional **336 fixtures** execute the entire `CD7E -> F142 -> 1AC0 /
13:36BB -> 38C5 -> 64CA -> 0F4A / 6:C3B9` path. Only FFF3 busy bits3/4
read clear as synthetic completion. Fixtures use RAM39=1, FFFF=13, zero
initial window configuration and four nonzero synthetic DAD3 values. No
burst engine or actual screen is emulated.

F142 adds BE16 **DBFD:DBFE** to the first/third fields and **DBFF:DC00** to
the second/fourth, modulo65536. It passes them as R6:R7, R4:R5, R2:R3 and
D84C:D84D. The callee13:36BB stores them in **D846..D84D** and prepares
**D84E..D859**, a 12-byte payload. Bytes3/6 combine the low nibbles of each
coordinate pair's high bytes; bytes4/5 and7/8 contain their low bytes. Bits
above bit11 are discarded by packing. Four offset pairs include arithmetic
wraps to check this behavior; they do not establish legal screen ranges.

The reference [ScalerOsdDrawWindow implementation](https://github.com/Kingdomwhisky/RTD-Scaler-TEST/blob/3d38340ec8518a8888fd5d8dbb181c2a7418e11c/Kernel/Scaler/ScalerFunction/Lib/Code/ScalerOSD/Windows/OsdDrawWindow.c#L59)
provides the same four-argument order, 12-byte layout, window address formulas,
rotation update and structure clearing. The **XStart/YStart/XEnd/YEnd** naming
is therefore strong source-correlated evidence for these firmware fields;
physical orientation/visibility are untested.

For the checked geometry, window selector6 gives control address **0118**.
The actual code prepares XDATA source **01:D84E**, count12, destination
port **0092**. Burst registers are 009F=0, FFF4=92, FFF6=13 (bank fixture),
FFF7:FFF8=D84E and FFF9:FFFA=000C. The hardware would transfer the prepared
buffer; this model checks register programming and does not perform that copy.

After the burst code returns under synthetic completion, the actual firmware
updates the low bit at control address **01A1** to0, then `2139` clears
**DC8B..DC91**. Explicit stacks are balanced. Earlier CA2A drawing, its
DA70.bit0 alternate route and the full menu entry remain excluded.

## Reproduce and precise continuation

```powershell
uv run --locked --offline python tools/map_osd_language_layout.py <local-V020.bin> --out docs/maps/osd-language-layout.json
```

[Derived check report](maps/osd-language-layout.json) contains no firmware
resources. [Language-list follow-up](OSD_LANGUAGE_LIST.md) now executes the
ordinary entry through RET for all21 stored languages under explicit synthetic
state and binds each name index to its segment/position; its lifecycle mode also
executes ordinary **9:C63A** apply and **9:FA18** exit. Next: DCC4:DCC5=02CC
consumers, modal/high-flag/re-entry cases, native glyphs and other dirty-save leaves.
DAD3's producer/units and real burst completion remain unproved.

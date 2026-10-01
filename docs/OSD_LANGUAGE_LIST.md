# Language list: resource segments, rendering positions and integrated entry

All evidence is offline on the pinned V020 image. This closes the ordinary
row32 command0 entry that [earlier layout checks](OSD_LANGUAGE_LAYOUT.md)
had intentionally split at drawing boundaries, and now follows ordinary preview,
apply and exit. Other modal/re-entry/high-flag variants and actual monitor
behavior remain outside these fixtures.

## Confirmed list resource and explicit index

The actual loop **10:D153..D1C1** iterates **D82F=0..20**. At D1BB,
`1A4E -> 1:DC4F` receives row `5+2*(index%8)`, column
`26+13*(index//8)` and R3=3. The text context **D853:D854:D855** is
**0E:00:index**. These style/row/column arguments are separate from the
window fields and setting selectors.

DC4F uses **FC8F -> E43B** to resolve text family0E/index0 to **code1:6D77**.
The subsequent actual DC8A..DCA2 loop skips D855 FF-delimited segments.
There are exactly **21 segments before1:6E1B**, the independently resolved
start of family09. **63 selection fixtures** check all21 indices with three
stored-language inputs each, stopping at DCA7 before rendering. The selected
pointer **D874:D875:D876** is FF:segment-address; DA03 remains unchanged.
Thus the list uses each entry's explicit index rather than using DA03 as its
name selector.

| Index | Segment start | Length | Row | Column | Partial base-font candidate |
|---:|---|---:|---:|---:|---|
| 0 | 1:6D77 | 7 | 5 | 26 | English |
| 1 | 1:6D7F | 8 | 7 | 26 | `Fran<8F>ais` |
| 2 | 1:6D88 | 7 | 9 | 26 | Deutsch |
| 3 | 1:6D90 | 7 | 11 | 26 | `Espa<B1>ol` |
| 4 | 1:6D98 | 8 | 13 | 26 | Italiano |
| 5 | 1:6DA1 | 10 | 15 | 26 | Nederlands |
| 6 | 1:6DAC | 7 | 17 | 26 | `Pycc<A4><AA><A9>` |
| 7 | 1:6DB4 | 6 | 19 | 26 | Polski |
| 8 | 1:6DBB | 7 | 5 | 39 | `<8D>e<C6>tina` |
| 9 | 1:6DC3 | 8 | 7 | 39 | Hrvatski |
| 10 | 1:6DCC | 7 | 9 | 39 | MMagyar |
| 11 | 1:6DD4 | 6 | 11 | 39 | `Rom<86>n<82>` |
| 12 | 1:6DDB | 9 | 13 | 39 | `Portugu<98>s` |
| 13 | 1:6DE5 | 6 | 15 | 39 | `T<CE>rk<8F>e` |
| 14 | 1:6DEC | 5 | 17 | 39 | Unresolved glyphs |
| 15 | 1:6DF2 | 5 | 19 | 39 | Unresolved glyphs |
| 16 | 1:6DF8 | 4 | 5 | 52 | Unresolved glyphs |
| 17 | 1:6DFD | 4 | 7 | 52 | Unresolved glyphs |
| 18 | 1:6E02 | 3 | 9 | 52 | Unresolved glyphs |
| 19 | 1:6E06 | 3 | 11 | 52 | Unresolved glyphs |
| 20 | 1:6E0A | 16 | 13 | 52 | Bahasa Indonesia |

Positions, pointer boundaries and segment lengths are **CONFIRMED**. The
names are **STRONG EVIDENCE / partial candidates**, reusing the atlas's
existing base-font decoder. Unknown glyph tokens and duplicated letters are
preserved; native-script identities14..19 and accented glyphs are not guessed.
The number of encoded glyph fragments is not necessarily a character count.

## Confirmed complete ordinary-entry fixtures

**21 fixtures execute9:F550 through top-level RET**, one for each valid stored
language. No drawing callee is skipped. Each makes exactly21 D1BB list calls,
with the arguments/context above, then returns with **DA6B=56** and
**DA48:DA49=00:stored-language**, preserving DA03. Each records116 window
burst preparations and3,213 control/address/data-port writes; these are
instruction effects in memory, not measured transfers or visible output.
Combined execution is **19,147,309 instructions**; every run stays below its
2,000,000-instruction bound and returns with balanced explicit stacks.

The fixtures inherit the verified Window model: only **FFF3 busy bits3/4**
read clear as synthetic completion. RAM39=1, FFFF=13, DAD3=60000000 and
DC09/DBFC=40 are explicit synthetic initialization. Burst-engine copies,
interrupts, actual timing and display visibility are not emulated. The runs
do not write FF55..FF5E hardware-I2C registers. This proves the integrated
code path under the stated fixture conditions, not live startup equivalence.

## Confirmed preview, apply and exit cycles

The `--lifecycle` campaign executes **21 complete cycles**, one from each
stored language, using the same explicit synthetic entry prerequisites:

1. Execute F550 entry, then command1/E7F9 preview increment with refresh.
2. Execute command2/FEEB ->E7F9 preview decrement back to the stored value.
3. Execute command0/C63A unchanged apply: no window preparation and no
   DA03/DA69/DA6C change.
4. Decrement preview again, including0-to20 wrapping, then execute full
   C63A changed apply through RET. DA03 becomes selected, DA69=1, DA6C=0B,
   DA6B stays56 and preview stays selected. Full drawing calls execute.
5. Execute command3/FA18 through RET: DA6B returns32; selected DA03 and
   DA69=1/DA6C=0B are retained. Save dispatch has not run in this cycle.

Changed apply also ends with **DCC4:DCC5=02:CC and direct bit25 cleared**,
via the verified FD52 leaf. The downstream meaning of that pair is not assigned
here. These cycles do not write FF55..FF5E and do not persist a setting.
The independent [save integration](OSD_LANGUAGE_UPDATE.md) establishes what
the pending event does when its dispatcher later runs.

**131,072 exit-gate fixtures** cover all256 DA68 values, all256 current
settings and DA83=0/7, stopping before FA36's transition call. FA18 selects
target32 when **DA68.bit6 is clear**, otherwise current DA6B; it calls
`1676 ->10:DE50`, then tail-calls `167C ->8:E7E4`. Only the ordinary
clear-bit6 target32 case has complete exit drawing execution here.

## Modification constraints and continuation

Each entry is selected by skipping FF delimiters from the same base. Changing
a segment's length moves later entry starts; the next family09 resource begins
immediately at6E1B. The list loop and language validator both have21 entries,
and preview wrapping is0..20. Adding/removing an entry would require reviewing
all three contracts, the font dispatch and geometry groups; none is approved
or patched here. Names/bytes are not ASCII strings.

```powershell
uv run --locked --offline python tools/map_osd_language_list.py <local-V020.bin> --lifecycle --out docs/maps/osd-language-list.json
```

Without `--lifecycle`, full entry still runs but apply/exit cycles are omitted.
`--segments-only` checks pointers and exit gates without integrated entry.
[Derived report](maps/osd-language-list.json) includes no resource payloads.
[Notification follow-up](OSD_NOTIFICATIONS.md) now resolves DCC4/DCC5 through
GET02/52 and maps GETCC's language protocol values. Indices14/15/16 correlate
to Simplified/Traditional Chinese/Japanese as strong source evidence; the
native glyphs remain undecoded. Next: **language SETCC mapping/save/redraw**,
then re-entry/modal/high-flag variants and remaining glyph fragments.

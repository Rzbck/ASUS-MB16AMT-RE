# Language preview, apply writer and display-event provenance

The extended [callback matrix](OSD_HANDLERS.md) separates the ordinary language
menu row **32** from its staged selection row **56**. These are DA6B setting
selectors, not language IDs. Language IDs remain numeric 0..20; their human
names are not yet mapped. All evidence is offline on the pinned V020 image.

## Confirmed preview and apply roots

| DA6B row56 command | Callback | Checked behavior |
|---|---|---|
| 0 | 9:C63A | Compare stored language against staged DA48:DA49; later C6B0 reads staged DA49 and updates DA03 |
| 1 | 9:E7F9 | Advance staged index, wrapping 20 to0 |
| 2 | 9:FEEB -> E7F9 | Decrease staged index, wrapping0 to20 |
| 3 | 9:FA18 | Separate transition callback; full effects remain open |

E7F9 calls A99C to read BE16 DA48:DA49, initializes lower bound D827:D828=0,
then calls `19D6 -> 8:B9A9` with upper20 and step1. Its setting56 branch
calculates the command-dependent result. A8D4 stores that result to
DA54:DA55; E821..E82B copies it into DA48:DA49. Execution stops before
`E831 -> 19DC -> 10:CA2A` refresh effects.

**10,752 fixtures** cover every staged index0..20, both preview callbacks and
every packed stored-language byte. Command1 gives `(staged+1)%21`, command2
`(staged-1)%21`; DA03 and DA69 stay unchanged at this boundary. The staged
selection is therefore distinct from the committed language.

## Confirmed committed-byte writer

C63A queries selector32 through the verified getter8:5FEF. With DA48=0,
equal staged/current low-six-bit values return via C743. All 64x64 pairs
are checked up to the changed-value boundary C652, before drawing side effects.

The later coherent tail **9:C6B0..C6C2** reads DA49, masks it with3F, and
updates DA03 as `(old&C0)|(DA49&3F)`. Helper **A93F** performs the write at
the supplied DPTR, then sets **DA69.bit0**, preserving other flags. These
contracts pass all65,536 old/staged byte pairs and256 dirty-flag cases.
The writer does not clamp to20; valid preview bounds and the separately
verified storage validator are distinct constraints.

The next call **167C -> 8:E7E4** writes **DA6C=0B** if DA69 is nonzero,
preserving DA69; zero DA69 leaves DA6C unchanged. All256 flag bytes with both
incoming carry values pass. The existing display-event dispatcher sends
0B to **9:BA6E**. This establishes a state-update to display-event connection;
BA6E's complete save/redraw effects remain to be followed.

```mermaid
flowchart LR
  P[Row56 command1/2: E7F9] --> V[DA48:DA49 preview0..20]
  V --> U[Row56 command0: C63A / C6B0 tail]
  U --> L[DA03 low6 committed language]
  U --> F[DA69.bit0]
  F --> E[E7E4: DA6C=0B]
  E --> H[9:BA6E effects still open]
  L --> T[Menu text segment / font selection]
```

The diagram composes checked subcontracts. Apply fixtures execute the writer
tail, not all drawing between C63A's comparison and that tail; preview fixtures
stop before their refresh call. No real display, storage write or command occurs.

## Why the generic numeric route is excluded for row32

The normal row32 command1/2 callbacks FD9D/FE7F call C031 **only when
DA68.bit6 is clear**, otherwise return (512 cases). C031 tests the same flag
and then selects its navigation branch C049. Thus those callbacks do not
establish a row32 path through C0E6's numeric adjustment branch.

Separately, **8:8B52 with selector32** does not update DA03: all65,536 packed
language/proposed-byte cases write only scratch D824=32. Language modification
must be followed through row56 staging/application rather than inferred from
the presence of a language query in the generic getter. This resolves the
previous next-target assumption without changing the verified getter contract.

## Reproduce and remaining work

```powershell
uv run --locked --offline python tools/map_osd_language_update.py <local-V020.bin> --out docs/maps/osd-language-update.json
```

[Derived checks](maps/osd-language-update.json) publish no resource bytes.
Next precise targets: **entry transition from row32 into row56**, preview
refresh **10:CA2A** and apply drawing, then **9:BA6E** and DA69 dirty/save/clear
lifecycle. Tie language names to each index through rendered resources.
Physical button labels, storage completion and the complete OSD map remain open.

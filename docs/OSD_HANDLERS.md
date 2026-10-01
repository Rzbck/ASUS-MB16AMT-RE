# DA6B/DA6D callback tables and verified traversal extension

The [input command producer](OSD_COMMANDS.md) feeds DA6D. Two consumers now
have checked pointer selection: normal `9:A23E..A26A` and alternate
`8:E49A..E4EB`. This maps callback addresses, not all handler effects or names.
The complete OSD map remains unfinished. Every check is static/offline.

## Normal table

At A23E, the caller forms `8FAF + 12*DA6B + 3*DA6D`, reads cell bytes1/2
into R2:R1, and calls common **2133**. That helper sets DPTR=R2:R1 and
jumps with A=0 in the current bank. The cell's leading byte is not loaded
by the caller; all 376 cells in the checked range have tag FF.

**376 fixtures** verify settings 00..5D with commands 0..3, including the
actual 2133 jump stopped before executing the selected callback. A23E has
no local setting/command guard. The range follows the normal/alternate
partition and coherent FF-tagged cells; it is not a proof that every pair
is reachable. Command4 mechanically indexes the next row; do not promote
such out-of-range reads to valid normal-table semantics.

Examples, using the table's local callback addresses:

| Setting | Command0 | Command1 | Command2 | Command3 |
|---|---|---|---|---|
| 00 | 9:FD5E | 9:FDD4 | 9:FDD7 | 9:FD5E |
| 01 | 9:FB43 | 9:F9AA | 9:FDDA | 9:FAC3 |
| 32 (DA03 language query) | 9:F550 | 9:FD9D | 9:FE7F | 9:FE82 |
| 33 (D9FD.bit6 inverse query) | 9:F074 | 9:F4B0 | 9:FE85 | 9:FE88 |
| 59 | 9:FB5F | 9:FC26 | 9:FEF1 | 9:FCC0 |
| 5D | 9:FC8A | 9:EB26 | 9:FDDD | 9:FD11 |

These row identities use the existing [setting-query contract](SETTING_QUERY.md).
They do not establish a physical button name. For row32, FE7F jumps to FD9D;
FE82 jumps to F406. Thus the two adjustment-side callbacks share one routine,
which can consult DA6D, rather than requiring separate language setters.

## Alternate table: carry-sensitive bounds

E49A clears scratch D821 and reads DA6B. Its checked range is **5E..A8**.
The table is addressed as `38C0 + 12*DA6B + 3*DA6D` in bank8.

**All 65,536 byte pairs** setting/command execute the actual guard:

- In-range settings, command0..3: select the corresponding callback (300 cases).
- In-range settings, command4/5: jump to FED6 -> F7D5 (150 cases).
- Other settings or command6..255: return without a callback.

The SUBB instructions retain carry between comparisons. Reading only their
immediate operands would give incorrect command bounds. All four columns are
selected, including column3's FED6 pointers. F7D5 clears DA6B and DA68.bit1
around its existing call to 18BC; that routine's full display effects are not
asserted by these selection fixtures.

## Improved CFG, without guessing runtime edges

The existing `analyze_banked_abi.traverse` now accepts optional explicit
`extra_seeds`. Its default traversal remains unchanged at **158,425** starts.
`map_osd_handlers.py` supplies **455 distinct callback entries** from the checked
cells. The resulting graph has **166,916 instruction starts**, adding **8,491**,
with **zero overlaps, zero reserved opcodes and no new unresolved indirect sites**.
The original twenty unresolved indirect sites still remain globally.

This recovers bodies previously absent from the default graph because the
common indirect helper hid their entry points. A pointer to common thunk165E
is resolved by the existing ABI. Successful graph traversal proves coherent
decode/reachability from these static roots, not functional hardware behavior.

## Shared callback prelude

Some callbacks call **1934 -> 10:FEB0** when DA83=07. Its body is now checked
in all **65,536 DA6B/old-DA83 combinations**: it initializes DBFD..DC00 to
00/24/04/08; setting0 writes DA83=07, other settings preserve DA83. The supplied
R7 command is not read by this helper. The field/palette interpretation remains
to be traced through their consumers; do not label the helper as a command
dispatcher simply because a caller loads R7 from DA6D.

These coherent callback/helper routes support the existing static bank model,
but do not establish physical bank switching on the running monitor.

## Reproduce and next precise work

```powershell
uv run --locked --offline python tools/map_osd_handlers.py <local-V020.bin> --out docs/maps/osd-handlers.json
```

The [complete checked cell matrix](maps/osd-handlers.json) includes all callback
addresses, guards and coverage counts without firmware bytes. Next:
**row32 -> 9:FD9D / FE7F -> 9:C031 -> C0E6**, separating navigation mode from
adjustment mode, then `19D6 -> 8:B9A9` and `1652 -> 8:8B52` to bridge language
read/update/display. Also follow DA6E repeat-flag resets using the extended CFG.
The shared prelude fields DBFD..DC00 still require downstream interpretation.

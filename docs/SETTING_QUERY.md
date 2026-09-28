# Static contract of 8:5FEF

Status: **CONFIRMED for the SHA-pinned V020 instruction stream**, assuming the
documented logical-to-physical static bank model. No hardware execution.

Entry `8:5FEF`, end-exclusive `8:65A0`, common thunk `1862`.
Inputs: byte R7 = selector; byte R5 = query mode. Output: byte R7.
Mode meanings are **STRONG EVIDENCE** from callers: 0 current, 1 upper bound,
2 lower bound, 3 adjustment step. Exact numeric behavior below is CONFIRMED.
This is a setting query, not an ADC/I2C acquisition function.

## Exact branch contract

`X[addr]` denotes an XDATA byte. Selector numbers are hexadecimal; numeric
results and shift counts below are decimal unless explicitly marked hex.
The complete 256-selector x mode contract is in `maps/setting-query-contract.csv`.

For mode 0:

| Selectors | Return R7 |
|---|---|
| 0F..16 | X[DA06] & 0Fh |
| 17..1B | X[DA0E] >> 4 |
| 1C,1D,1E | X[DA3D], X[DA3E], X[DA3F] respectively |
| 1F,20,21,22 | X[DA41], X[DA42], X[DA43], X[DA08] |
| 23 | v=X[DA0E]&3; if v==1 and DA68.bit2==0 return 0, else v |
| 24 | X[DA17] |
| 25 | 1 if X[DA44]==0, else 0 |
| 28 | inverse of D9FD.bit5 |
| 29 | inverse of D9FE.bit6 |
| 2A | inverse of DA00.bit0 |
| 2B | X[D9F9] |
| 2C | inverse of D9FF.bit5 |
| 03,2D,42 | inverse of D9FF.bit4 |
| 2E | inverse of DA00.bit3 |
| 04,43 | inverse of D9FF.bit7 |
| 05 | inverse of D9FF.bit6 |
| 2F | inverse of DA0F.bit0 |
| 30 | inverse of D9FE.bit5 |
| 32 | X[DA03] & 3Fh |
| 33 | inverse of D9FD.bit6 |
| 35 | inverse of D9FD.bit1 |
| 36 | 1, in **every** mode |
| 37,38,39 | low nibbles of DA0B, DA0C, DA0D |
| 44 | X[DA04] |
| 45 | inverse of D9FD.bit2 |
| 46 | X[DA07] |
| 50,51,52 | clamp(X[DA21/DA22/DA23] - 28, 0, 100) |
| 0C | X[DA0A] & 0Fh |
| 5D | DA92.bit4 |
| all other selectors | 0 |

Mode 1: 0F..16 -> 7; 17..1B -> 4; 1C..1E,21,22,24,2B,46,50..52 -> 100;
1F -> 5; 20 -> 2; 44 -> 120; 32 -> 20; 0C -> 8; boolean rows,23,25,5D -> 1;
37..39 and unknown selectors -> 0. Selector 36 remains 1.

Mode 2: 44 -> 10; 36 -> 1; everything else -> 0.

Mode 3: 21 -> 10; 22,46 -> 20; 24 -> 25; 44 -> 10; 5D -> 0;
all remaining selectors, **including unknown selectors**, -> 1.

Modes 04..FF: selector 36 -> 1; all others -> 0.

Mode 0 does not generally clamp stored values to mode-1 maxima. For example,
selector 1C returns DA3D verbatim even if it exceeds 100. Do not infer a byte's
meaning from a neighboring mode-1 return of 100.

## Reads, writes and callees

The prologue writes selector to D833, mode to D834, and 1 to D835. The mode-3
branch at 5FFB simply repeats the same write of 1; it adds no hidden input.
Other direct reads are exactly the state fields in the table above.

Direct callees: `8:A917`, `8:A926`, `8:A929`, `8:A944`, `8:AA4B`, `8:AA5B`;
one tail transfer at `8:612C` via `1B74 -> 6:C2D4` for selectors 50..52/mode 0.

- A917 supplies max=128 in R4:R5, min=28 in R2:R3, center=78 at D83C:D83D.
- A926/A929 extract bit5; AA5B extracts bit6; A944 shifts the masked nibble;
  AA4B tests whether mode is 3. These are local memory/arithmetic helpers.
- `6:C2D4..C3B8` clamps the 16-bit input, computes the two-sided percentage
  around a center, then rounds to an integer. With (max,min,center)=(128,28,78),
  the exact byte-input result is `clamp(value-28,0,100)`.
- The conversion's helpers at ADC3, ADED/ADF0, ADF7, AE21, AE2D, AE36, AE3F,
  AE46, AE4D, AE59, AE6F, AEA4 ultimately use the common arithmetic routines
  1F2E (multiply), 1FB9 (32-bit division), 1DC8 (16-bit division).

All writes in the tested transitive query closure are confined to
**D833..D83D**, the query/conversion scratch slots. All other accesses are reads
of the listed internal state. No I2C, ADC, PMIC, bank register or peripheral
register is accessed by this closure. This says nothing yet about writers of
the stored state. R0..R7, A, B, DPTR and flags should be treated as scratch
unless a particular caller's instruction flow establishes preservation.

The arithmetic matches public
[`UserCommonAdjustRealValueToPercent`](https://github.com/Kingdomwhisky/RTD-Scaler-TEST/blob/3d38340ec8518a8888fd5d8dbb181c2a7418e11c/Kernel/User%20Common%20Function/Code/UserCommonAdjust.c#L1003).
Functional correspondence is STRONG EVIDENCE; no ASUS symbol name is asserted.

## Callers and exact path into the renderer

`maps/setting-query-callers.csv` inventories every raw LCALL/LJMP reference to
thunk 1862, plus direct 8:5FEF references, distinguishing CFG-reached sites.
Many callers in bank 9 are behind unresolved dispatch tables, so raw candidates
must not be silently promoted to reachable calls. The existing CFG establishes
19 callsites through 1862 at the initial audit; later table recovery may expand it.

At `10:C507`, the caller reads DA6B via incoming DPTR, puts it in R7, sets R5=0
and calls thunk 1862 at C50B. It zero-extends the returned R7 and writes the
32-bit renderer input at D838..D83B using 20C4. Caller C41E invokes thunk 1670.
Thus the exact source is whichever setting DA6B selects; it is not an automatic
battery-read path. For example DA6B=50h selects DA21 and the conversion above.

At `10:D5CF/D5DE/D5ED`, the selector in D824 is queried with modes 1/2/0;
the results go to D82C/D82D/the 16-bit scratch value D82E:D82F. That value
subsequently feeds `10:E816 -> E9CA -> E9F7 -> 1670 -> 1:EAEB`.
This establishes one concrete provenance chain for the second renderer caller.
D82E:D82F is reused scratch across many functions, not a persistent global sensor.

## Verification and limitations

```powershell
uv run --no-project tools/analyze_value_provenance.py '<V020.bin>' --out work/provenance
```

The independent high-level contract is compared with a bounded interpreter of
the actual instructions: 65,536 selector/mode combinations, 65,280 further
mode-0 byte-state cases, and eight independently varied coupled-field cases;
**130,824 checks pass**. The byte conversions cover every possible source value.
At most 1,596 instructions execute per tested invocation.

860 of 862 main-function instruction starts are exercised. The two unvisited
LJMPs are provably infeasible: 611C requires a selector other than 50/51/52 after
the enclosing range check and exclusions; 622C requires a one-bit value to be
neither zero nor one. All other conditional outcomes in the main body are covered.
`setting-query-xdata.csv` and `setting-query-transfers.csv` retain access/callsite
evidence; `setting-query-summary.json` records test counts and assumptions.

This interpreter is deliberately limited: no hardware or interrupt model, no
AC/OV/parity semantics, and separate explicit-byte/call stacks. The tested paths
must not consume those unmodeled mechanisms. Passing these tests corroborates
manual static reconstruction; it is not a live-device validation.

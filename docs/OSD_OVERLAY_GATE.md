# DA72 refresh gate and deferred language release

## Confirmed instructions and paths

9:B7CE sets DA72 bit3, preserving every other bit;9:FC1B clears bits3/4,
preserving every other bit. All256 initial bytes verify each leaf (512 checks).
The default checked CFG has three direct calls to B7CE:9:BD38,9:C882,9:EC93.
This inventory does not claim complete indirect/address-propagated writers.

The [verifier](../tools/map_osd_overlay_gate.py) executes48 complete producer
fixtures: entries9:BD2F/C84C/EC90 x initial DA72=00/08/10/18 x DA6B=00/56 x
dirty language bit0 clear/set. Every path ends with DA72 bit3 set and retains
the stored language and dirty byte. Every original drawing callee executes.

Representative outputs for DA72=0 and initial dirtybit0=1:

| Entry | Initial DA6B | Final DA72 | Final DA6B | Final DA6C | Prepared window frames |
|---|---:|---:|---:|---:|---:|
| 9:BD2F | 00 or56 | 18 | 00 | 0B | 3 |
| 9:C84C | 00 | 08 | 00 | 0B | 2 |
| 9:C84C | 56 | 08 | 54 | 0B | 8 |
| 9:EC90 | 00 or56 | 08 | 00 | 0B | 1 |

Values are hexadecimal except counts. The full [derived report](maps/osd-overlay-gate.json)
includes all initial states, step counts and outputs. Existing Window supplies
synthetic burst completion; physical visibility is unverified. Producer calls
with an already-pending dirty byte can publish0B through F439 before setting
the gate. Thus gate-set alone does not imply DA6C=0 in every runtime state.

## Deferred SET can reach the existing save path

168 composed fixtures (21 languages x4 packed high-bit combinations x2 gate
bytes08/18) execute the original receive SETCC then9:FC11:

```text
SETCC with DA72.bit3 set
  -> DA03 applied, DA69.bit0 set, DA6C remains0
9:FC11
  ->15F8 /10:F439
      ->167C /8:E7E4 publishesDA6C=0B; DA6B becomes0
  ->15FE /1:FA88 withR7=0,R5=1
  ->9:FC1B clearsDA72.bits3/4
pending9:B8B2 /BA6E
  ->15C2 /8:DDB3 validator ->01D0 page writer
```

All168 release states retain the applied packed DA03 and dirtybit0, end with
DA72=0/menu state0/event0B, and have balanced interpreter stacks. Each state
continues through eight storage fixtures (DA87 bit3 x four profiles):
1,344 saves use the original validator/page code with synthetic FF5D success.
The payload equals D9FD..DA20 and byte6 contains the applied packed language.
DA69/DA6C finish0. No real storage completion is claimed.

**STRONG EVIDENCE:** bit3 acts as an OSD overlay ownership/refresh-suppression
gate: drawing-producing paths set it, SET tails respect it, and FC11 resets
the OSD before clearing it. Exact physical screen names remain unassigned.
The composed release proves a route exists, not that every deferred runtime
SET necessarily reaches FC11. Interrupts and later event producers are absent.

Next precise target:9:A1D1..A212, including its conditional clear9:A203..A20C
versus FC11 call. Determine the state/flag gates and connect them to the menu
command dispatcher before assigning modal or popup semantics.

```powershell
uv run --locked --offline python tools/map_osd_overlay_gate.py $fw --out docs/maps/osd-overlay-gate.json
```

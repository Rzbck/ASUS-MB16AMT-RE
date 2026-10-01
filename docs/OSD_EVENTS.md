# OSD display-event dispatch and timer producers

Offline instruction-level verification on SHA-pinned V020; the existing static
bank model applies. No hardware command or patch. Reproduced by
`tools/map_osd_atlas.py`; derived contract in
[osd-atlas.json](maps/osd-atlas.json), field `display_event_dispatch`.

## Consumer and clear boundary

`9:B8B2` clears D820, reads DA6C and invokes the inline byte-switch helper
210D at B8BB. The table B8BE..B8DF selects:

| DA6C (hex) | Target |
|---|---|
| 01, 0C | 9:B8E0 |
| 02 | 9:B935 |
| 07, 08 | 9:B956 |
| 09 | 9:BA15 |
| 0A | 9:BA1D |
| 0B | 9:BA6E |
| 0E | 9:BAC2 |
| 0F | 9:BAD3 |
| Other byte | 9:BAE1 |

The six-instruction prologue/dispatch was executed for all 256 DA6C bytes,
stopping precisely before each target with an intentional instruction budget.
The independent transcribed table matches every target. D820 is the only
XDATA write at this boundary; DA6C retains its input value.

The tail `9:BAE1` writes zero to DA6C and returns. All 256 input-byte clear
cases pass. It is both the switch default and a shared handler exit. Handler
side effects/branches are not established by this dispatch-only check.

This supports interpreting DA6C as a **pending display-event byte** (strong
semantic evidence). It does not identify a raw key, debounce state or complete
menu-state enum. DA6B, DA6D, D823 and the timer event ID are distinct fields or
namespaces.

## Five timer-to-display links

The established `4:EC1F` timer dispatcher selects these exact leaf writers:

| Timer R7 (hex) | Writer | DA6C value | Consumer target |
|---|---|---|---|
| 04 | 4:ECD8 | 01 | 9:B8E0 |
| 05 | 4:ECD1 | 02 | 9:B935 |
| 0C | 4:EF47 | 09 | 9:BA15 |
| 1A | 4:ECDF | 0C | 9:B8E0 |
| 1C | 4:F0E1 | 0E | 9:BAC2 |

Each leaf was executed independently and writes only DA6C. Its address was
also cross-checked against the already recovered 36-entry timer table. Thus
timer 0C writes display code 09; equality of numeric IDs must not be assumed.
The05/0C producer is now verified in [OSD_NAVIGATION_GUARDS.md](OSD_NAVIGATION_GUARDS.md):
fallback modes4/6 cancel0D/0E and request05/0C withargument5000. Physical
time units remain unverified. Other conditional writers remain to be traced.

## Complete event09 consumer and nested event overwrite

[map_osd_event09.py](../tools/map_osd_event09.py) and its
[report](maps/osd-event09.json) execute256 complete original event09 paths:
four menu states00/32/56/58 x four DA72 flags00/08/10/18 x four DCC9 bytes
00/23/80/FF x two DCCA bit6 states x dirtybit0 clear/set. Window supplies the
existing synthetic burst completion; the explicit snapshot includes bank13,
RAM39=1/nonzeroDAD3 and otherwise zero state. This is bounded fixture coverage.

```text
9:B8B2 ->BA15 ->15F8/10:F439 (reset OSD)
  ->R7=3 ->BACE ->18C8/7:F82D (status writer)
  ->BAE1 (clear DA6C) ->RET
```

The complete fixtures end with DA6B=0, DCC9 low nibble=3 and DA6C=0.
Packed DA03, DA72, dirty DA69 and DCCA survive. No storage/I2C FF55..FF5E
write occurs, and interpreter stacks balance. Physical visibility/status
names remain unproved; this assigns no name to DCC9 low nibble3.

**Confirmed local overwrite:** with initial DA69 bit0 set, nested F439 calls
E7E4 and writes DA6C=0B at8:E829. The outer handler then writes DA6C=0 at
9:BAE5. Dirtybit0 remains set and this event09 handler does not save it.
This is not proof of permanent global loss: later producers/interrupts may
republish0B. With dirtybit0 clear, only the final zero event write occurs.

The independent **7:F82D status-writer** checks131,072 packed DCC9/DCCA
byte fixtures with R7=2/3. It replaces DCC9 low nibble with R7&0F while
preserving the high nibble. Only R7=2 clears DCCA bit6 (when set); event09
supplies3 and does not change DCCA.

## Event02 execution boundary

Zero-clock whole event02 fixtures reach **2:FA66..FAAE**, a wait that compares
RAM42:43 snapshots and a local elapsed counter. With9C70 bit2 clear and no
interrupts, the zero-clock snapshot does not advance and hits the interpreter
budget. Setting9C70 bit2 in a separate offline fixture takes the early wait
exit, but then reaches unsupported opcode82 at2:FDF8. Neither is a complete
event02 proof; no busy wait or unsupported instruction was silently skipped.

Next precise work: add and verify standard MCS-51 **ANL C,bit (82h)** support
in the existing interpreter, then reconstruct event02 under explicit wait-exit
fixtures and separately trace the real RAM42:43 producer. Keep synthetic
completion separate from physical timing and display behavior.

## Caller integration

The current decoded graph establishes:

```text
6:FC3E LCALL 1472 -> 9:FB97
9:FBA3 LCALL 9CD9
9:FBA6 LCALL B8B2
9:FBA9 LCALL BED3
9:FBAC LCALL E0AF
9:FBAF LJMP D8D7
```

The call at 6:FC3E is conditional in its enclosing routine. This identifies
the service integration and its surrounding work, without proving live call
frequency or that any specific handler is reached on the monitor.

Next precise target: the conditional service at **6:FC39** and the preceding
**9:9CD9** dispatch, following their real input producers. Resolve whether
those inputs are display/system state before linking them to buttons. In
parallel, classify DA6C handlers through their calls into `10:D760` and the
existing label/render paths; preserve conditional branches.

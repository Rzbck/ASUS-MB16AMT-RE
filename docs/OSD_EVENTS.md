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
Scheduling, time units and conditional writers remain to be traced.

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

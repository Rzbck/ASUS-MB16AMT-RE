# Software clock ISR and delay coefficients

CONFIRMED on pinned V020, entirely offline. The common vector **002B jumps
to0140**. The original0140..0189 ISR executes through RETI in all65,536
clock-word fixtures; [verifier](../tools/map_osd_clock.py),
[derived report](maps/osd-clock.json).

At0171 it increments RAM43. If that byte wraps to zero,0177 increments RAM42.
Thus the big-endian RAM42:43 word advances once modulo65536 per serviced
interrupt. This supplies a producer for the counter read by the verified
[timer scheduler](OSD_COMMANDS.md) and [event02 wait](OSD_EVENTS.md).
It does not establish the interrupt frequency or physical milliseconds.

The ISR saves/restores A, DPTR and PSW. It preserves FFF4 through scratch
DCA6, clears SFR bitCF and sets RAM bits1E/1F. Its XDATA effects are:

- DCA6 receives the initial FFF4, which is restored before RETI;
- FFEB becomes `(old & 7F) | 08`;
- FFEA is ORed with40 only when `(FFAD & 7) >= 5`.

An additional1,024 fixtures cover every FFAD byte with four FFEB/FFEA pairs,
including top-bit clearing and existing flags. Stacks balance; there are no
other XDATA writes on the checked ISR path. No actual interrupt is delivered.

At **0:FD6C**, R7 selects two software delay-loop coefficients:

| R7 | RAM39 | RAM36 |
|---|---:|---:|
| 2 | 26 | 21 |
| 1 | 3 | 6 |
| Other byte | 2 | 2 |

These coefficient values are decimal. All256 selector bytes execute the
original leaf. The caller and source of R7 remain open; no CPU frequency or
duration is inferred from these numbers. Earlier event02 fixtures with
RAM36/RAM39=1 were explicitly synthetic and are not an initialization claim.

Next precise targets: **interrupt002B enable/reload/clock-source setup**, and
the coherent caller of **FD6C** that derives R7. Also trace5:D893..D89F, which
resets RAM42:43 in the existing scheduler helper. Preserve the distinction
between instruction-level clock provenance and a measured wall-clock rate.

```powershell
uv run --locked --offline python tools/map_osd_clock.py $fw --out docs/maps/osd-clock.json
```

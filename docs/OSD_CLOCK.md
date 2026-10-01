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
original leaf. No CPU frequency or duration is inferred from these numbers.
Earlier event02 fixtures with
RAM36/RAM39=1 were explicitly synthetic and are not an initialization claim.

## Caller-selected coefficients, not register-derived selectors

The verified direct caller prefixes provide **R7=0 at0:6396**, **R7=2 at
7:D5BB** and **R7=1 at7:D5F5**. The bank7 calls use0D3A ->0:FD5B.
FD5B reads FFEE/FFED, extracts FFEE bits5..2 into R5/B, then falls into FD6C.
It never replaces the incoming R7.196,608 whole FD5B fixtures cover all
FFEE/FFED byte pairs for selectors0/1/2 and prove that neither register changes
the coefficients. The physical meanings of the caller modes remain unassigned.

## Counter reset and active-deadline rebasing

At5:D893 the helper clears bit1E and RAM42:43, then visits all16 slots at
D92D+3*i. For an active (nonzero ID) slot it retains the ID and sets:

```text
deadline = max(old_deadline - BE16(D82D:D82E), 0)
```

An empty slot's deadline bytes remain untouched. At completion D82D:D82E
is cleared and R6:R7 returns0.262,144 isolated slot checks cover every old
deadline against elapsed0/1/8000/FFFF.2,304 complete reset/rebase fixtures
cover six boundary deadlines x six elapsed values x all16 active-slot positions
x four initial clock words. The other empty slots contain BEEF to verify
their preservation. No IRQ interleaves; bit1E's asynchronous recheck atD89A
is not a concurrency proof. The upstream condition selecting this reset is
still open. Keeping an ID with deadline0 does not itself dispatch its event.

**STRONG EVIDENCE:** the ISR matches the pinned Realtek
[SysTimerIntProc2](https://github.com/Kingdomwhisky/RTD-Scaler-TEST/blob/3d38340ec8518a8888fd5d8dbb181c2a7418e11c/Kernel/System/Code/SysTimer.c#L432):
FFF4 backup, Timer2 flag clear, watchdog register handling and timer-counter
increment. This supports a system Timer2 interpretation; physical period
remains unverified.

Next precise targets: **interrupt002B enable/reload/clock-source setup** and
the upstream **5:D83F..D893 reset decision**, then caller clock-mode identities.
Preserve the distinction between clock provenance and a wall-clock rate.

```powershell
uv run --locked --offline python tools/map_osd_clock.py $fw --out docs/maps/osd-clock.json
```

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

## Timer2 count/reload setup with Timer0/1 stopped

[map_osd_timer2_setup.py](../tools/map_osd_timer2_setup.py) verifies65,536
mode/FFED fixtures and1,024 prior D928 fixtures. Every original CA9B..CC1F
instruction executes with TR0/TR1 initially clear. The running Timer0/1
deadline-conversion branches are outside this proof.

| R7 mode | First count (TH2:TL2) | Reload (RCAP2H:RCAP2L) |
|---|---|---|
| 01 | E373 | E373 |
| 02 | F6E2 | F6E2 |
| 04 | 00D3 | F6E2 |
| Other, including00 | FB56 | FB56 |

CA9B saves the mode in D822 and prepares D823..D827. It disables ET2/TR2,
clears TF2, writes count bytes to SFR CC/CD and reload bytes to CA/CB,
clears RAM bit1E, then enables ET2/TR2. The mode2 FFED branch affects D928
(3 if FFED bits5..2 equal1, else2), but not the checked count/reload bytes.
Mode1 sets D928=1; other modes preserve it. Full derived data and limitations
are in [osd-timer2-setup.json](maps/osd-timer2-setup.json).

The checked initialization prefix0:63BF supplies R7=0 and calls0D16 ->5:CA9B.
Earlier0:6399..63BD clears/stops timer flags, selects Timer0/1 mode11,
clears T2CON bit0 (auto-reload), sets Timer2 priority and global interrupt
enable. This prefix is decoded, not a complete initialization execution proof.
No hardware register is written by the verifier; all SFR/XDATA are bytearrays.

Mode4's first count and reload differ. No constant physical tick period can
be assigned from reload alone. Actual clock-source/divider setup and running
Timer0/1 adjustment remain open; register counts are not measured durations.

## Running Timer0/1 conversion during mode changes

[map_osd_timer_conversion.py](../tools/map_osd_timer_conversion.py) and its
[report](maps/osd-timer-conversion.json) verify the original32-bit multiply/
divide helpers over all65,536 previous-word values for each rate7308/2333
(131,072 arithmetic fixtures), followed by640 complete CA9B setup fixtures.

When the D928 mode target changes and the corresponding timer was running,
the new backup is:

```text
backup = (FFFF - floor(rate * previous / 1000)) mod65536
rate = 7308 for mode1; 2333 for mode2
```

Timer0 reads D98A:D98B and writes D982:D983. Timer1 reads D98C:D98D and
writes D984:D985. Mode2 target is3 when FFED bits5..2 equal1, otherwise2;
mode1 target is1. An unchanged target preserves the old backup words.
Large arithmetic fixtures include truncation/wrap; they are not additional
legal runtime duration assignments.

For initially running timers in modes1/2, the tail compares backup against
the current reload bytes: D95D/D95F forTimer0, D95E/D960 forTimer1.
If different, it temporarily disables that timer/interrupt, copies the backup
to those bytes and TL/TH SFRs, then enables the timer/interrupt. Stopped timers
and modes0/4 preserve their current reloads. The640 complete fixtures cover
four modes x two FFED branches x four histories x four running masks x five
previous-word values. They use fixed unequal current/backup snapshots; the
equal-current fast path and asynchronous timer progress remain open.

The conversion structure matches pinned
[ScalerTimerSetTimerCount](https://github.com/Kingdomwhisky/RTD-Scaler-TEST/blob/3d38340ec8518a8888fd5d8dbb181c2a7418e11c/Kernel/Scaler/ScalerCommonFunction/Code/ScalerCommonTimerFunction.c#L1218).
Names such as previous/backup count and mode-switch continuity are strong
source-correlated interpretations, not physical timing measurements.
The existing [battery timing evidence](BATTERY_LIVE_PROXY.md) already ties
D98C:D98D=03E8 to5:E268 called with argument1 by4:F3B3. Thus this conversion
path intersects the Timer1 acquisition clock; it does not itself read SOC.

## Reset decision before event scheduling

[map_osd_clock_reset.py](../tools/map_osd_clock_reset.py) and its
[report](maps/osd-clock-reset.json) verify196,608 argument-sweep fixtures,
196,608 clock-sweep fixtures and300 complete static-clock calls.

**5:D83F** receives R6:R7 as argument and snapshots the software counter
through F73D. Its checked contract is:

```text
effective = min(argument, 61000)
if snapshot_clock + effective > 61000:
    reset clock; rebase active slots; return0
else:
    return snapshot_clock
```

The sum here is mathematical (no16-bit truncation). The original code first
compares the wrapped16-bit sum to61000, then detects wrap separately.
Together these implement the condition above. Equality61000 does not reset.
With clock0, even argumentFFFF is clamped and does not reset. Clamping is
local to the reset decision; it does not prove every caller's scheduling
argument is independently clamped.

All300 complete calls execute F73D and the original16-slot rebasing code
with stable RAM42:43. They cover ten boundary arguments x ten clock values
x active slot0/7/15; empty slots contain BEEF deadline bytes to verify their
preservation. After reset, the active deadline is reduced by the original
snapshot with saturation, clock/return become0, and its ID survives.

The structure matches pinned
[ScalerTimerCheckTimerEvent](https://github.com/Kingdomwhisky/RTD-Scaler-TEST/blob/3d38340ec8518a8888fd5d8dbb181c2a7418e11c/Kernel/Scaler/ScalerCommonFunction/Code/ScalerCommonTimerFunction.c#L2495).
**STRONG EVIDENCE:** this is the scheduler's pre-allocation counter-range
check. Reference units are nominal milliseconds; no physical61-second
measurement is claimed for V020. F73D's concurrent snapshot/retry behavior
remains separate from these static-clock fixtures.

Next precise targets: **F73D snapshot guard**, clock-source/divider setup and
equal-current conversion fast path. Timer0 previous-word provenance and
physical frequency remain open. Every verification is offline.
Preserve the distinction between clock provenance and a wall-clock rate.

```powershell
uv run --locked --offline python tools/map_osd_clock.py $fw --out docs/maps/osd-clock.json
uv run --locked --offline python tools/map_osd_timer2_setup.py $fw --out docs/maps/osd-timer2-setup.json
uv run --locked --offline python tools/map_osd_timer_conversion.py $fw --out docs/maps/osd-timer-conversion.json
uv run --locked --offline python tools/map_osd_clock_reset.py $fw --out docs/maps/osd-clock-reset.json
```

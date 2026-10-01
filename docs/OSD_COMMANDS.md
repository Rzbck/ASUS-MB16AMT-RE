# Input words, OSD command publication and repeat timer

This continues [OSD_INPUT.md](OSD_INPUT.md) from the current/previous words
DC9E:DC9F and DCA0:DCA1. The checks execute actual SHA-pinned instructions
offline. No hardware command or physical timing measurement occurs.

## Translation branch contract

`2:E20F` reloads the current word through F20F and calls `DD54` at E27E.
The initial DD54 branch is exhaustive over all 65,536 words:

| Exact input word | Initial branch |
|---|---|
| 0004 | 2:DDA7 |
| 0008 | 2:DDF0 |
| 0010 | 2:DE3D |
| 0020 | 2:DE95 |
| 0080 | 2:DD7B |
| Every other word, including combinations | 2:DEF9 |

There is no generic bit-priority arbitration in this initial dispatch.
Word 0001 also has the separate E6B6 consumer; its absence here does not mean
the physical input is unused.

Most accepted branches reload F20F, place a **command code** in R5 and tail
call F9FB. DA6D command codes are a separate namespace from the input masks,
DA6B setting selectors, DA6C display events and timer IDs.

**105 whole-branch fixtures** use display/system states DCB7&1F=3/4/6,
D9FD.bit1=0 and DA09 high nibble=0, for seven settings and five input masks.
For ordinary tested settings 00/03/04/05 the resulting commands are:

| Input word | R5 command at F9FB |
|---|---|
| 0004 | 2 |
| 0008 | 1 |
| 0010 | 3 |
| 0020 | 0 |
| 0080 | 0 |

Verified special cases in those fixtures:

- Setting 59: inputs 4/8 directly store DA6D=7; inputs 16/32 translate to
  commands 1/2 and clear DA70.bit4 with the supplied DA09 high nibble=0.
- Setting 5D: inputs 4/8 translate to 7; 16/32 translate to 1/2.
- Setting 01: input 32 translates to 1. Inputs 4/8/32 copy the low nibble
  from DA0C/DA0D/DA0B respectively into DA0A, preserving its high nibble.
  This now ties input translation to the previously verified category source.
- Input 128 sets DA68.bit6 for settings 03/04/05.

These are exact fixture results, not all setting/mode combinations. Physical
button names, special-setting names and a universal command-label assignment
remain unproved. E20F has earlier hold/shortcut/suppression handling, including
E346 and FE77; DD54 alone is not the complete physical-key behavior.

## F9FB: change detection and repeat contract

Inputs are R6:R7 mask and R5 command; comparison uses current and previous
runtime words. No peripheral is read on this checked producer path.

1. If `((current XOR previous) AND mask) != 0`, write DA6D=command, set
   DA6E.bit4 and return without scheduling. This detects changed masked bits;
   it is not intrinsically restricted to a rising edge.
2. Otherwise, exact masks 0002/0040 clear DA6E.bit3; all others set it.
3. If bit3 is clear, return. If bit2 is set, write DA6D=command and return.
4. Otherwise, call `0B7E -> 5:E77F` for timer event 01, with R6:R7=500
   when bit4 is set, or 20 when clear.

**139,344 cases** check the producer: every 16-bit mask with a masked change,
all DA6E flag bytes and command codes 0..7 for twelve representative masks and
three histories, plus unrelated-bit changes. The flag semantics are measured
instruction behavior, not names inferred from a numerical match.

The default DD54 branch `DEF9` clears DA6E.bits2/3 and requests cancellation
of timer 01 through `0B84 -> 5:F920` (256 flag cases). It does **not** clear
DA6E.bit4 or DA6D in that tail. This includes zero input and rejected combined
words; those distinctions matter when following flag lifecycle upstream.

## Timer connection and storage

The recovered [36-entry timer dispatcher](DA86_TIMER.md) maps event 01 to
`4:ECA3`. That leaf sets DA6E.bit2, preserving the other bits (256 checks).
It enables the later F9FB publication branch; the leaf itself does not write
DA6D.

The actual E77F scheduler uses sixteen 3-byte slots at **D92D..D95C**:
event byte followed by BE16 deadline. Across 128 first-free-slot fixtures
(all sixteen positions, two repeat arguments, four fixed software clocks),
it stores event 01 and `RAM42:43 + argument`. Sixteen further fixtures show an
existing event 01/deadline is left unchanged; a full table of event 02 entries
also remains unchanged. These are 145 scheduler checks in total.

F920 cancellation clears the first matching event byte and retains the two
deadline bytes (sixteen slot-position checks). No interrupts or expiry engine
are fabricated in these fixtures. The primary Realtek timer API corroborates
millisecond arguments as discussed in [DA86_TIMER.md](DA86_TIMER.md), but
physical repeat cadence and the consumer's complete flag reset sequence are
still open. Do not claim that held inputs repeat at a measured 20 ms rate.

## Reproduce and next target

```powershell
uv run --locked --offline python tools/map_osd_commands.py <local-V020.bin> --out docs/maps/osd-commands.json
```

The [derived report](maps/osd-commands.json) publishes contracts/counts only.
Next precise target: **9:A23E..A26A**, where DA6B and DA6D select a function
pointer from `9:8FAF + 12*setting + 3*command`, then call common **2133**.
Also trace the guarded alternate table at **8:E49A..E4EB**, and the DA6E.bit2/4
reset sites after command handling. Recover handler identities before naming
commands or buttons. The full OSD mapping remains unfinished.

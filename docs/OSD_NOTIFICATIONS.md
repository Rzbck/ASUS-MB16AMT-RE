# OSD change reporting: DCC4/DCC5, GET02/52 and language GETCC

The [complete language lifecycle](OSD_LANGUAGE_LIST.md) ends changed apply
with DCC4:DCC5=02:CC and direct bit25 cleared. This document follows that
record through the actual DDC GET dispatcher and reply builder, offline.
The existing GetVcp interpreter boundary stops before9:1298 transport;
**no DDC/monitor command is sent**.

## Confirmed marker and consumption

**9:FD52** accepts R7=changed identifier, sets DCC4=2/DCC5=R7 and clears
direct bit25. All65,536 R7/RAM24 combinations verify both writes and preservation
of the other RAM24 bits. The marker itself does not set dirty/save flags.

The inline table at **9:A3D1** selects:

| GET selector | Handler | Checked reply and state effects |
|---|---|---|
| 02 | A462 ->A71E | Type0, max2, currentDCC4; record/bit25 unchanged |
| 52 | A5B7 | Bit25clear: currentDCC5, then setbit25; bit25set: current0 without readingDCC5. Type0/maxFF in both cases; DCC4 becomes1; DCC5 retained |
| CC | A726 | Type0/max31, current translated from DA03 low6; record/bit25 unchanged |

The original dispatcher, **13:6699** reply builder and **187A** checksum
execute. All512 status fixtures, 2,048 active-control fixtures and168 valid
language fixtures produce packets whose XOR, including checksum, is50h.
The active-control fixtures cover all256 recorded identifiers, both bit25
states and DCC4 values0/1/2/FF. Arbitrary states are mechanical coverage,
not additional valid enum assignments.

One composed marker/read sequence returns:

```text
FD52(R7=CC)
GET02 -> current2
GET52 -> currentCC; setbit25, DCC4=1
GET02 -> current1
GET52 -> current0
```

**GET52 has a runtime state effect.** It acknowledges/consumes the modeled
notification even though the protocol operation is a GET. This distinction
matters for future strict read-only observation; no such query is sent here.

The pinned [DDC identifier definitions](https://github.com/Kingdomwhisky/RTD-Scaler-TEST/blob/3d38340ec8518a8888fd5d8dbb181c2a7418e11c/Kernel/User%20Common%20Function/Header/UserCommonDdcciDefine.h#L81)
name02 New Control Value,52 Active Control andCC OSD Language. Their
correspondence to the exact firmware handlers is **strong source evidence**;
the reply/state contracts above are **CONFIRMED**. The reference's52 handler
is empty, so its implementation is not substituted for ASUS's checked code.

## Confirmed language-to-protocol conversion

GETCC reads **DA03&3F**, then `MOVC code9:9426+index`. It does not return
the internal index directly. The checked valid-language mapping is:

| Internal index | GETCC current (hex) |
|---:|---|
| 0 | 02 |
| 1 | 03 |
| 2 | 04 |
| 3 | 0A |
| 4 | 05 |
| 5 | 14 |
| 6 | 09 |
| 7 | 1E |
| 8 | 12 |
| 9 | 11 |
| 10 | 1A |
| 11 | 1F |
| 12 | 08 |
| 13 | 0C |
| 14 | 0D |
| 15 | 01 |
| 16 | 06 |
| 17 | 07 |
| 18 | 30 |
| 19 | 23 |
| 20 | 31 |

All21 indices, all four DA03 high-bit combinations and both bit25 states
pass. No DA03/DA69/DA6C mutation occurs. GETCC itself does not clamp low6;
invalid21..63 are outside this verified valid-language contract.

The reference [language SET cases](https://github.com/Kingdomwhisky/RTD-Scaler-TEST/blob/3d38340ec8518a8888fd5d8dbb181c2a7418e11c/User/RTD%20Series/RTD2014Osd/Code/RTD2014Ddcci.c#L1117)
explicitly associate protocol0D with Simplified Chinese,01 with Traditional
Chinese and06 with Japanese. Combined with the verified conversion, indices
**14/15/16** have those identities as **STRONG EVIDENCE**. Their rendered
native glyphs are still not independently decoded. The other unresolved
scripts are not assigned by adjacency or presumed ASUS ordering.

## Connection to the prior ED marker audit

The previously classified **9:F1C0 ->FD52(R7=ED)** uses the same marker
and GET52 consumer as language changes. It reports a changed control ID;
the literal is not receive-side SET-handler evidence. This strengthens the
shared OSD/DDC change-report architecture without reopening the eliminated
immediate-constant heuristic or asserting new battery/PMIC behavior.

## Reproduce and continuation

```powershell
uv run --locked --offline python tools/map_osd_notifications.py <local-V020.bin> --out docs/maps/osd-notifications.json
```

[Derived verification report](maps/osd-notifications.json) exports no firmware
resources. Next precise target: **language SETCC mapping into DA03** and its
validation/redraw/save effects, then compare it with the ordinary OSD apply
path. Native glyph decoding and modal/re-entry variants remain unfinished.

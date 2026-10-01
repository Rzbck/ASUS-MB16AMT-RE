# Receive-side language SET CC

CONFIRMED offline against the pinned V020 firmware. The existing dispatcher
9:9452 selects 9:9883 for opcode D993=CC. It reads D995 (low payload byte)
and dispatches through the inline table at9:988A. The table ends98CD and
defaults to997A. Its21 accepted codes are exactly the inverse of
[GETCC](OSD_NOTIFICATIONS.md)'s table, with the same internal indices0..20.
See the [derived branch map](maps/osd-language-set.json).

Each accepted code calls9:D227, preserving DA03 bits7..6 and replacing the
low6 with the internal index. Equal selections are written too. Unsupported
codes retain DA03. **Both accepted and unsupported codes OR DA69 bit0** via
997A ->9C99. Thus an unsupported language code can request a save even
though no language changes. This does not prove that the later save succeeds.

The dispatcher prologue zeros D820, writes DCC5=CC and clears direct bit25.
It retains DCC4, unlike the OSD apply marker FD52 which sets DCC4=2.
Neither DA6C nor DA87 is written on the checked paths. D994 is never read.

The shared tail9:9CA2 calls D2A3, which reads DA72, rotates right three times,
and masks1F. The following test of accumulator bit0 therefore tests original
DA72 bit3 regardless of incoming carry. When that bit is set, the handler
returns. When clear, it calls15F8 ->10:F439, whose entry calls18BC ->13:6803
then invokes multiple5:F920 selector operations. The verifier stops before
F439 in this earlier boundary check; complete-path fixtures follow below.

The [verifier](../tools/map_osd_language_set.py) runs actual instructions for
65,536 low-code/packed-old-language combinations,65,536 low/high-payload
combinations,1,024 dirty-flag fixtures and1,024 DA72 gate fixtures. The latter
two use valid codes02/31 and unsupported00/FF. All writes stay in an in-memory
bytearray; no DDC command or hardware operation is sent.

```powershell
uv run --locked --offline python tools/map_osd_language_set.py $fw --out docs/maps/osd-language-set.json
```

## Complete refresh and event/save integration

The [complete-path verifier](../tools/map_osd_language_refresh.py) and
[report](maps/osd-language-refresh.json) extend the earlier boundary:
1,344 fixtures cover21 languages x4 DA03 high2 x2 DA72 bit3 x2 DA87 bit3 x4
profiles. All original refresh callees execute; no drawing/selector leaf is
skipped. The initial hardware state is synthetic (bank13, RAM39=1,
DAD3=60,000,000, burst busy bits clear). This is bounded fixture coverage,
not every possible F439 branch.

With DA72 bit3 clear, **10:F439 ->167C/8:E7E4 publishes DA6C=0B** and the
routine finishes with DA6B=0. The applied packed DA03 and dirty bit0 survive.
Register/OSD port writes occur, but these fixtures prepare no window burst
frames and issue no modeled FF55..FF5E I2C writes during SET/refresh.
Unsupported codes00/FF also complete this reset/event path while retaining
the old language.

Each of the672 clear-gate states continues through actual9:B8B2/BA6E and
8:DDB3 validation into01D0 storage. The existing storage model supplies
synthetic FF5D success. The36-byte page payload equals D9FD..DA20 and byte6
is the applied packed DA03; DA69/DA6C both finish0. DA87 bit3 selects the
existing0E or32+36*profile destination. Real storage completion is unproved.

With DA72 bit3 set, the other672 complete SETs bypass F439, retain DA6B=56,
leave DA6C=0, and keep dirty bit0. Calling the event dispatcher immediately
afterward still leaves the dirty bit pending: SET did not publish event0B.
This does not prove permanent loss; later event producers/interrupts have
not been executed in this verifier. [OSD_OVERLAY_GATE.md](OSD_OVERLAY_GATE.md)
now verifies the setters/clearers and a composed FC11 release/save route.

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
F439; its complete effects and the semantic meaning of DA72 bit3 remain open.

The [verifier](../tools/map_osd_language_set.py) runs actual instructions for
65,536 low-code/packed-old-language combinations,65,536 low/high-payload
combinations,1,024 dirty-flag fixtures and1,024 DA72 gate fixtures. The latter
two use valid codes02/31 and unsupported00/FF. All writes stay in an in-memory
bytearray; no DDC command or hardware operation is sent.

```powershell
uv run --locked --offline python tools/map_osd_language_set.py $fw --out docs/maps/osd-language-set.json
```

Next: execute10:F439 through its original selector callees, determine whether
it publishes a save event, and trace the producers of DA72 bit3. Keep the
verified SET dirty mark distinct from OSD apply's DA6C=0B publication.

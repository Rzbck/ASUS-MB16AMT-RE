# Charge policy — VCP ED to internal state

## Status

**CONFIRMED / STRONG EVIDENCE** for ASUS MB16AMT V020.

The Set-VCP dispatch is now reconstructed from the real DDC receive buffer:

```text
D992 == 0x03 (Set VCP)
  -> bank9:9452
D993 = VCP opcode
  -> inline 0:210D byte-switch
VCP ED
  -> bank9:9C7A
```

The exact ED handler reads `D995` (the Set-VCP low value byte) and updates `D9FF`:

```text
ED = 0   -> D9FF.bit7 = 1
ED != 0  -> D9FF.bit7 = 0
both      -> D9FF.bit4 = 0
then      -> DA69.bit0 = 1
```

The live experiment independently established:

- `ED=0` => `Charging From NB/PC`
- `ED=1` => `No Charging From NB/PC`

Therefore `D9FF.bit7` is **strong evidence** for an active-high internal policy state meaning approximately **charge from notebook/PC allowed**.

`DA69.bit0` is used by many unrelated setting/update paths and remains classified as a generic dirty/update trigger until a power-specific downstream path is proven.

## Current consumer triage

Direct reads of `D9FF.bit7` include several paths that appear to normalize the bit into settings/UI scratch state, for example:

- bank8 around `635E`
- bank9 around `A802`
- bank10 around `BEC8`

The strongest policy evaluators are now:

- bank9 `E703` / `E70D`, which loads the full `D9FF` byte and extracts bit7 through helper entry `AA2E`, then returns a small status via `R5`;
- bank9 `EBE1` / `EC06`, which likewise evaluates `D9FF.bit7` together with `DA50` and other `D9FF` bits, returning status `0` or `6` via `R5`/`R7`.

Earlier triage also listed bank9 `CFC3`, but the focused helper trace corrects that interpretation: `CFC3` calls helper entry `A994`, which performs `MOVX A,@DPTR` followed by `ANL A,#20`. With `DPTR=D9FF`, this tests **D9FF.bit5**, not bit7. Therefore `CFC3` is no longer considered a direct charge-policy-bit consumer.

## Eliminated downstream sink: bank13:3DE6

`E703` can feed its status directly to bank13 `3DE6`, but the focused sink trace and the public Realtek register map show this branch is a **display/scaler configuration reaction**, not a charger/PMIC bridge.

Evidence includes writes through helpers that reach page-0 scaler registers such as:

- `0x006A`, documented in the public Realtek tree as D-Dither Common Control;
- `0x006C`, documented as Overlay Control.

Therefore bank13 `3DE6` is retained as a real consumer of the policy-derived status but is **not promoted to power hardware**.

## Next step

Run:

```powershell
python tools/trace_charge_bit7_callers.py <verified-v020.bin>
```

This tracer inventories:

1. all direct `D9FF` + `ANL #80` sites,
2. every decoded caller of `9:AA2A` (the helper that loads `D9FF` and extracts bit7),
3. every caller of `9:AA2E` (generic bit7 extraction), with local context so D9FF provenance can be checked,
4. nearby XDATA references for each caller.

Promotion rule: do not call a path "power management" merely because it consumes `D9FF.bit7`; require downstream calls/XDATA to reach Type-C, PMIC, charger, or otherwise independently identified power-state logic.

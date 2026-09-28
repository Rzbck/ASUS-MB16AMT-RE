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

## Next step

Run:

```powershell
python tools/trace_charge_policy_callers.py <verified-v020.bin>
```

The tracer prints directly to the terminal and follows:

1. exact callers of `E703`, `EBE1`, `E759`, and `E7F2`,
2. the bridge around `E759/E7F2`,
3. XDATA touched by the caller region,
4. immediate use of the returned `R5/R7` status.

Promotion rule: do not call a path "power management" merely because it reads `D9FF.bit7`; require downstream calls/XDATA to reach Type-C, PMIC, charger, or otherwise independently identified power-state logic.

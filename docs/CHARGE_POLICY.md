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

More promising policy/state-machine regions combine the charge-policy bit with other runtime state before branching:

- bank9 around `E70D`
- bank9 around `EBE1` / `EC06`
- bank9 around `CFC3`

These are the next static-analysis targets.

## Next step

Run:

```powershell
python tools/trace_charge_policy_consumers.py <verified-v020.bin>
```

The tracer prints directly to the terminal and inventories:

1. direct `D9FF.bit7` consumers,
2. helper semantics around the bit extractors,
3. incoming control-flow into the promising regions,
4. XDATA references and outgoing calls from those regions.

Promotion rule: do not call a path "power management" merely because it reads `D9FF.bit7`; require downstream calls/XDATA to reach Type-C, PMIC, charger, or otherwise independently identified power-state logic.

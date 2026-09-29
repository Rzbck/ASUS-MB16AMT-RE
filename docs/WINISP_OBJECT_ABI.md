# WinIsp object-relative resolver and read ABI

Verified offline on SHA256
`13242a1dc8f1d263cb4235ae50b6409855e259fbf3fe894bc06584389a16334c`.
VAs use preferred image base 10000000. This is host-side provenance, not MCU RAM.

## Resolver

`10003DE0` loads singleton pointer `[1020BCFC]` into ESI. The module path
argument reaches `LoadLibraryW` through IAT `101A2358` at `10003E0D`; the module
handle is stored at object+4. `GetProcAddress` IAT `101A2264` is loaded into EDI.
Following the explicit CFG reconstructs 119 resolution/store pairs in 118 slots
(DDCCIRead is stored twice), rather than assuming every nearby ASCII API name
belongs to a nearby call. The derived table is `maps/winisp-object-slots.csv`.

| Object offset | Resolved export | GetProcAddress call | Store |
|---|---|---|---|
| 074 | I2CReadEx | 10003F03 | 10003F05 |
| 0A4 | ReadReg | 1000413A | 1000413C |
| 0AC | ReadRegs | 1000416A | 1000416C |
| 0BC | ReadRegEx | 100041CA | 100041CC |
| 0C4 | ReadRegsEx | 100041FA | 100041FC |
| 0D4 | ReadSysDevice | 1000425A | 1000425C |
| 0DC | ReadWordSysDevice | 1000428A | 1000428C |
| 110 | NativeRead | 100043C2 | 100043C4 |

The factory at `10021D70` allocates 210h bytes, installs vtable `101D8EA4`
at `10021EF1`, and publishes the object at `10021F00`. Its configuration uses
the key `WinComm.dll`; the actual loader receives the resolved path.

## Calls

Vtable +0C points to `10003530`: thiscall ECX object, two stack arguments.
It loads `[ECX+BC]`, pushes output pointer then address, calls the export at
`1000354C`, cleans eight bytes, and returns with `RET 8`. The export is cdecl:
`ReadRegEx(address, byte* output)`, EAX status, two 32-bit argument slots.

Command dispatcher `1001F200`, table `1001F968`, command **15h** enters
`1001F705`, loads object+0C4 at `1001F732`, and calls at `1001F75A`, with
16 bytes of caller cleanup at `1001F764`. Argument order is address, count,
output pointer, increment. The stream contains a big-endian 16-bit address,
big-endian 16-bit count and increment byte after the command byte.

**Shared call warning:** command 19h loads **ReadMcuRegs** at `1001F876` and
joins this same indirect call. The whole-CFG merged EAX is therefore unknown;
the ReadRegsEx proof is explicitly conditioned on dispatch command 15h.
Do not label `1001F75A` unconditionally as ReadRegsEx.

Object-proven virtual ReadRegEx uses include `1001AC9D`, `1001ACAE`,
`1001B596`, `1001B625`, `1001B6B9`, `1001E64B`, `1001E67A`, `1001F62C`,
`100216D3`, `100216E8`, `100216FD`. This is a bounded candidate-root analysis
(74 roots), not an exhaustive call graph or proof of runtime reachability.

Cross-check against WinComm proves the export accesses only the effective
16-bit address for this register API. Full-width argument passing does **not**
establish the MCU's XDATA address space. See `LIVE_READ_BENCH.md` for selector
writes, unsupported NativeRead, and the actual live backend.

## Reproduce and limits

```powershell
uv run --locked python tools/soc_recon_deep.py "$env:TEMP/MB16AMT_RE/fw" --objects
uv run --locked python tools/test_x86_object_flow.py
```

The engine follows instruction boundaries, explicit branch/jump-table edges,
and a fixed-point join retaining equal facts only. Partial register writes kill
parent facts; calls clobber volatile registers. Unknown indirect edges stop.
Known singleton/vtable identity and callee-saved registers rely on the profiled
binary and x86 ABI; opaque callee memory mutations and concurrent replacement
are not modeled. No DLL is loaded by this analysis.

Older deep byte-window resolver heuristics are now marked CANDIDATE. They must
not be used as ABI proof merely because the resolver and API string are close.

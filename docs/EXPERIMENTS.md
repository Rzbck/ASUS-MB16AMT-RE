# Key experiments

## Charge-policy A/B

At 100% battery, switching the OSD from `Charging From NB/PC` to `No Charging From NB/PC` changed exactly one supported VCP:

- `ED`: current `0 -> 1`, max `1`
- total changes: `1`

This is the strongest confirmed runtime mapping in the project.

## Battery 100% -> 99% VCP comparison

With charging disabled, the battery eventually dropped to 99%. Only four supported VCPs changed:

- `02`: `1 -> 2`
- `10`: `0 -> 100`
- `52`: `0 -> 96`
- `CA`: `1 -> 2`

Vendor VCPs after the drop were: `E0=1`, `E3=100`, `E4=0`, `E9=0`, `EB=0`, `ED=1`, `F0=0`, `F1=1`, `FD=1`.

No VCP tracked SOC. In particular `E3` remained 100 while actual SOC was 99%.

## Internal ReadMcuReg comparison 74% -> 73%

Observed environment:

- AutoDetect: success
- DebugMode: `2`
- ISP slave: `0x94`
- continuous slave: `0x96`
- initial `ReadMcuReg(0x23)` returned success with value `0x00`

At both 74% and 73%, five passes over addresses `00..FF` produced:

- `256/256` stable addresses
- `0` non-zero values
- `0` changed registers across the SOC drop

Therefore this runtime path is not exposing useful live SOC/XDATA.

## Signature/service handshake

The tested ASUS/Realtek `77 11` handshake request repeatedly produced a DDC NULL reply (`6E 80 BE`) rather than the expected reference handshake response.

## Direct debug switch

A targeted `77 55` change-to-debug request did not activate the Realtek `0x6A` debug slave:

- `0x6E` was accessible before the request
- the write itself returned success
- `0x6E` remained accessible afterward
- a debug write to `0x6A` failed with `0x2B09`
- normal `0x6E` was still active at the end

## Generic fuel-gauge addresses

Read-only probes of common families all returned `0x2B0A` / no response:

- TI bq27xxx/bq274xx at `0xAA`
- MAX1704x at `0x6C`
- 0x0B-style battery at `0x16`

## RL6492 reference PMIC at 0xE0

Five read-only samples of reference SY9329 registers `04`, `06`, `07`, `08` all returned `0x2B0A` on the MB16AMT USB-I2C path.

## Power / black-screen experiment

VCP `D6=4` caused logical display removal and Windows topology reconfiguration. It was rejected for the black-screen use case.

The validated replacement is a black topmost overlay plus brightness 0, with brightness restored afterward.

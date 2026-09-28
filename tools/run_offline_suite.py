"""Run the reproducible, read-only V020 analysis suite with one command.

The firmware stays local. The script verifies its exact SHA-256 before launching
any analyzer and never communicates with the monitor.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib
import shutil
import subprocess
import sys

EXPECTED_SHA256 = "1e75681279bf974d2810e6d2ed91aabbeda35de3fabe1881733aa8a12319cb0c"
EXPECTED_SIZE = 0xE0000
ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"


def run(argv: list[str]) -> None:
    print("\n+", " ".join(argv), flush=True)
    subprocess.run(argv, cwd=ROOT, check=True)


def verify_firmware(path: Path) -> None:
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if len(data) != EXPECTED_SIZE:
        raise SystemExit(f"Refusing firmware size {len(data)}; expected {EXPECTED_SIZE}")
    if digest != EXPECTED_SHA256:
        raise SystemExit(f"Refusing firmware SHA256 {digest}; expected {EXPECTED_SHA256}")
    print(f"Verified V020: {path}")
    print(f"SHA256: {digest}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("firmware", type=Path, help="local extracted V020 .bin path")
    ap.add_argument("--out", type=Path, default=ROOT / "work" / "suite",
                    help="derived-output directory (default: work/suite)")
    ap.add_argument("--quick", action="store_true",
                    help="skip the exhaustive 8:5FEF provenance/emulation pass")
    ap.add_argument("--skip-powershell", action="store_true",
                    help="skip the two PowerShell static mappers")
    args = ap.parse_args()

    firmware = args.firmware.expanduser().resolve()
    out = args.out.expanduser().resolve()
    verify_firmware(firmware)
    out.mkdir(parents=True, exist_ok=True)

    py = sys.executable
    run([py, str(TOOLS / "analyze_banked_abi.py"), str(firmware),
         "--out", str(out / "abi")])
    run([py, str(TOOLS / "analyze_numeric_renderer.py"), str(firmware),
         "--out", str(out / "numeric-renderer.json")])
    run([py, str(TOOLS / "analyze_vcp_dispatch.py"), str(firmware),
         "--out", str(out / "vcp-dispatch")])

    if not args.quick:
        run([py, str(TOOLS / "analyze_value_provenance.py"), str(firmware),
             "--out", str(out / "setting-query")])

    if not args.skip_powershell:
        pwsh = shutil.which("pwsh")
        if pwsh:
            run([pwsh, "-NoProfile", "-File", str(TOOLS / "Analyze-FirmwareMap.ps1"),
                 "-FirmwarePath", str(firmware), "-OutputDirectory", str(out / "static-map")])
            run([pwsh, "-NoProfile", "-File", str(TOOLS / "Find-BankSwitchSignatures.ps1"),
                 "-FirmwarePath", str(firmware), "-OutputDirectory", str(out / "bank-switch")])
        else:
            print("\nPowerShell 7 (pwsh) not found; Python analyses completed."
                  " Re-run with pwsh installed to include PS1 mappers.")

    print(f"\nOffline suite complete: {out}")
    print("No device I/O was performed; firmware input was read-only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

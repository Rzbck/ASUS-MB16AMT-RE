"""Fail CI if the public repository contains obvious personal/device identifiers,
secrets, or proprietary binary payloads.

This intentionally scans tracked files only. It is a guardrail, not a substitute
for reviewing Git history before publishing sensitive material.
"""
from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_SUFFIXES = {
    ".bin", ".exe", ".dll", ".sfx", ".rar", ".zip",
    ".dump", ".rom", ".flash", ".hex",
}

TEXT_PATTERNS = [
    (
        "absolute Windows user path",
        re.compile(r"(?i)\b[A-Z]:\\Users\\(?!<|%USERNAME%|USERNAME\\|USER\\)[^\\/\r\n]+\\"),
    ),
    (
        "absolute macOS/Linux home path",
        re.compile(r"(?i)(?<![\w])/(?:Users|home)/(?!<|user/|username/|runner/)[^/\s]+/"),
    ),
    (
        "device-specific DisplayLink parent suffix",
        re.compile(r"(?i)VID_17E9&PID_437B\\[A-Z0-9_-]{8,}"),
    ),
    (
        "explicit observed serial field",
        re.compile(r"(?i)\bobserved\s+serial\s*[:=]\s*[A-Z0-9_-]{6,}"),
    ),
    (
        "GitHub token",
        re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    ),
    (
        "OpenAI-style API key",
        re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    ),
    (
        "AWS access key",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    ),
    (
        "Slack token",
        re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    ),
]

EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
ALLOWED_EMAIL_DOMAINS = {"users.noreply.github.com", "example.com", "example.org"}


def tracked_files() -> list[Path]:
    raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    return [ROOT / p.decode("utf-8") for p in raw.split(b"\0") if p]


def main() -> int:
    problems: list[str] = []

    for path in tracked_files():
        rel = path.relative_to(ROOT).as_posix()

        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            problems.append(f"{rel}: forbidden binary/archive suffix {path.suffix}")
            continue

        try:
            data = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            # A non-text tracked file is suspicious in this documentation/tooling repo.
            problems.append(f"{rel}: tracked file is not readable UTF-8 text")
            continue

        for label, pattern in TEXT_PATTERNS:
            for match in pattern.finditer(data):
                line = data.count("\n", 0, match.start()) + 1
                problems.append(f"{rel}:{line}: {label}")

        for match in EMAIL_RE.finditer(data):
            domain = match.group(0).rsplit("@", 1)[1].lower()
            if domain not in ALLOWED_EMAIL_DOMAINS:
                line = data.count("\n", 0, match.start()) + 1
                problems.append(f"{rel}:{line}: non-allowlisted email address")

    if problems:
        print("PUBLIC REPOSITORY GUARD FAILED", file=sys.stderr)
        for problem in problems:
            print(f" - {problem}", file=sys.stderr)
        print("\nReview the match before publishing. Do not add the sensitive value to an allowlist.", file=sys.stderr)
        return 1

    print("Public repository guard: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

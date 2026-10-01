"""Importing the core pulls in none of the HTTP or JWT dependencies."""

from __future__ import annotations

import subprocess
import sys

FORBIDDEN = (
    "fastapi",
    "starlette",
    "joserfc",
    "httpx",
    "xtr_http_kernel",
    "xtr_dependency_injection",
    "xtr_security_http",
    "xtr_security",
    "xtr_security_jwt",
)


def test_importing_the_core_stays_within_the_core() -> None:
    program = (
        "import sys\n"
        "import xtr_security_core\n"
        f"forbidden = {FORBIDDEN!r}\n"
        "leaked = sorted(name for name in forbidden if name in sys.modules)\n"
        "print(','.join(leaked))\n"
    )

    result = subprocess.run(  # noqa: S603 — a fixed program on this interpreter, no untrusted input
        [sys.executable, "-c", program],
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == ""

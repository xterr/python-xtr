"""Importing the security bundle pulls in none of the JWT dependencies."""

from __future__ import annotations

import subprocess
import sys

FORBIDDEN = (
    "xtr_security_jwt",
    "joserfc",
)


def test_importing_the_bundle_pulls_in_no_jwt_dependency() -> None:
    program = (
        "import sys\n"
        "import xtr_security\n"
        "import xtr_security.bundle\n"
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

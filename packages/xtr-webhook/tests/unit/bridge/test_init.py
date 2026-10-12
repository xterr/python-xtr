"""The import layering the bridge tree encodes, enforced.

The sending core works with no HTTP client installed, so only the bridge may
import one — or the resolver library the guard resolves hosts with. These are
read from the source rather than trusted.
"""

from __future__ import annotations

import pathlib

_SRC = pathlib.Path(__file__).resolve().parents[3] / "src" / "xtr_webhook"
_ALLOWED = ("bridge/httpx/", "bundle/_http_client.py")
_DRIVERS = ("import httpx", "from httpx", "import anyio", "from anyio")


def test_the_bridge_is_the_only_place_that_names_the_http_client() -> None:
    """The moment anything else imports httpx or anyio at module top level, the
    package stops importing without the ``client`` extra installed."""
    offenders = [
        str(path.relative_to(_SRC))
        for path in sorted(_SRC.rglob("*.py"))
        if not str(path.relative_to(_SRC)).startswith(_ALLOWED[0])
        and str(path.relative_to(_SRC)) != _ALLOWED[1]
        and any(line.startswith(_DRIVERS) for line in path.read_text().splitlines())
    ]

    assert offenders == []

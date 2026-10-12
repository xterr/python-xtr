"""The library imports none of the edges that sit on top of it.

The grants, entities, repositories, response types and servers are
framework-neutral: an application builds them by hand, so nothing here may
reach for the web framework, the bundle that wires this library into an
application, the container or the ORM. This package is the library and nothing
else, so every module it ships is walked and checked — a module added later is
covered without anyone remembering to list it.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_IMPORT_PACKAGE = "xtr_security_oauth2_server_core"
_SOURCE = Path(__file__).resolve().parents[2] / "src" / _IMPORT_PACKAGE

#: What a library module must not pull in: the web framework the bundle's
#: controllers adapt the library to, the bundle itself and the security family's
#: bundle, the container the bundle plugs into, and the ORM only the bundle's
#: persistence layer knows about.
FORBIDDEN = (
    "xtr_security_oauth2_server",
    "xtr_security",
    "fastapi",
    "starlette",
    "wireup",
    "xtr_dependency_injection",
    "xtr_orm",
    "sqlalchemy",
)


def _module_name(relative: str) -> str:
    """Return the dotted name a module path under the import package is imported by."""
    parts = relative.removesuffix(".py").split("/")
    if parts[-1] == "__init__":
        _ = parts.pop()
    return ".".join([_IMPORT_PACKAGE, *parts])


def _library_modules() -> tuple[str, ...]:
    """Return every module this library ships."""
    relatives = sorted(path.relative_to(_SOURCE).as_posix() for path in _SOURCE.rglob("*.py"))
    return tuple(_module_name(relative) for relative in relatives)


LIBRARY_MODULES = _library_modules()


def test_the_library_modules_are_found() -> None:
    assert f"{_IMPORT_PACKAGE}.exception.oauth2_error" in LIBRARY_MODULES


def test_the_servers_and_grants_are_walked() -> None:
    assert f"{_IMPORT_PACKAGE}.authorization_server" in LIBRARY_MODULES
    assert f"{_IMPORT_PACKAGE}.grant.abstract_grant" in LIBRARY_MODULES
    assert f"{_IMPORT_PACKAGE}.resource_server" in LIBRARY_MODULES


def test_importing_the_library_pulls_in_none_of_the_edges() -> None:
    program = (
        "import sys\n"
        f"for module in {LIBRARY_MODULES!r}:\n"
        "    __import__(module)\n"
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

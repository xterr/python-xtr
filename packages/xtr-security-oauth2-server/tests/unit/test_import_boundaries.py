"""The protocol library imports none of the edges that sit on top of it.

The grants, entities, repositories and response types are framework-neutral: an
application builds them by hand, so nothing below the HTTP edge may reach for
the web framework, the security family's bundle or the ORM. Only the parts that
*are* an edge may, and those are the paths named in ``ALLOWED`` — everything
else is walked and checked, so a module added anywhere later is covered without
anyone remembering to list it.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_IMPORT_PACKAGE = "xtr_security_oauth2_server"
_SOURCE = Path(__file__).resolve().parents[2] / "src" / _IMPORT_PACKAGE

#: What a library module must not pull in: the web framework the controllers
#: adapt the library to, the family's bundle the wiring plugs into, and the ORM
#: only the persistence layer knows about.
FORBIDDEN = (
    "fastapi",
    "starlette",
    "xtr_security",
    "xtr_orm",
)

#: The edges allowed to import them, as paths under the import package; a path
#: naming a directory covers every module beneath it.
ALLOWED = (
    "bundle",
    "controller",
    "factory",
    "manager/orm",
    "persistence",
    "routes.py",
    "security",
    "service/credentials_revoker",
)


def _is_edge(relative: str) -> bool:
    """Tell whether a module path under the import package is one of the edges."""
    return any(relative == allowed or relative.startswith(f"{allowed}/") for allowed in ALLOWED)


def _module_name(relative: str) -> str:
    """Return the dotted name a module path under the import package is imported by."""
    parts = relative.removesuffix(".py").split("/")
    if parts[-1] == "__init__":
        _ = parts.pop()
    return ".".join([_IMPORT_PACKAGE, *parts])


def _library_modules() -> tuple[str, ...]:
    """Return every library module of the package, the edges left out."""
    relatives = sorted(path.relative_to(_SOURCE).as_posix() for path in _SOURCE.rglob("*.py"))
    return tuple(_module_name(relative) for relative in relatives if not _is_edge(relative))


LIBRARY_MODULES = _library_modules()


def test_the_library_modules_are_found() -> None:
    assert f"{_IMPORT_PACKAGE}.exception.oauth2_error" in LIBRARY_MODULES


def test_an_edge_is_left_out_of_the_walk() -> None:
    assert _is_edge("routes.py")
    assert _is_edge("manager/orm/access_token_manager.py")
    assert not _is_edge("manager/access_token_manager_interface.py")


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

"""The console entry point: ``uvx xtr-cli <command>``, or ``xtr <command>`` once installed.

A console of its own, not an application's kernel: it runs before there is an
application to boot.
"""

from __future__ import annotations

from xtr_console import Application

from . import (
    __version__,
    command,  # noqa: F401  # pyright: ignore[reportUnusedImport] — declares the commands
)

__all__ = ["main"]

_DESCRIPTION = "Creates a new xtr application — a console or a web application — and serves it."


def main() -> None:
    """Build the console application and run it, exiting with its code."""
    application = Application(name="xtr", version=__version__, description=_DESCRIPTION)
    raise SystemExit(application.run())


if __name__ == "__main__":
    main()

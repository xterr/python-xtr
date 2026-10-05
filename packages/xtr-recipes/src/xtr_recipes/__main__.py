"""The console entry point: ``uv run xtr-recipes <command>``.

A console of its own rather than part of an application's kernel: the
application may not build before or after a recipe runs — a bundle can refuse
the build until the configuration file its recipe writes exists — so the tool
that writes it cannot need the application to boot.
"""

from __future__ import annotations

from xtr_console import Application

from . import (
    __version__,
    command,  # noqa: F401  # pyright: ignore[reportUnusedImport] — declares the commands
)

__all__ = ["main"]

_DESCRIPTION = "Applies the recipes of a project's dependencies, and undoes them."


def main() -> None:
    """Build the recipes console application and run it, exiting with its code."""
    application = Application(
        name="xtr-recipes",
        version=__version__,
        description=_DESCRIPTION,
    )
    raise SystemExit(application.run())


if __name__ == "__main__":
    main()

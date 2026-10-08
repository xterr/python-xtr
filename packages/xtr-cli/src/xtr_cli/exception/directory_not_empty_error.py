"""A project directory that already holds something a project would clash with."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from .cli_error import CliError

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["DirectoryNotEmptyError"]


@final
class DirectoryNotEmptyError(CliError):
    """The directory to scaffold into is a file, or already holds files.

    Nothing is ever written over: a project starts in a directory that is
    missing or holds nothing but version-control and editor metadata.

    Attributes:
        directory: The directory asked for.
        found: The entries that are in the way, sorted.
    """

    directory: Path
    found: tuple[str, ...]

    def __init__(self, directory: Path, found: tuple[str, ...]) -> None:
        """Record the directory and what is already in it."""
        self.directory = directory
        self.found = found
        listed = ", ".join(found[:5]) + (", …" if len(found) > 5 else "")  # noqa: PLR2004 — a preview.
        super().__init__(f"{directory} is not empty ({listed}): choose a new directory")

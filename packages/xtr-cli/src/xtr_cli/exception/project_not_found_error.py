"""No project at or above the directory a command was run from."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from .cli_error import CliError

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["ProjectNotFoundError"]


@final
class ProjectNotFoundError(CliError):
    """No ``pyproject.toml`` lies at or above the directory searched.

    Attributes:
        directory: Where the search started.
    """

    directory: Path

    def __init__(self, directory: Path) -> None:
        """Record where the search started."""
        self.directory = directory
        super().__init__(f"no pyproject.toml in {directory} or above it: pass --project-dir")

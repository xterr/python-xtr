"""No application project could be resolved to apply recipes to."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from .recipes_error import RecipesError

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["ProjectNotFoundError"]


@final
class ProjectNotFoundError(RecipesError):
    """The project, or the application package inside it, is not where expected.

    Raised when no ``pyproject.toml`` lies at or above the directory
    searched, and when not exactly one package under ``src/`` or the project
    root holds a ``kernel.py`` — the file that marks the application package.

    Attributes:
        directory: The directory that was searched.
        reason: What was looked for and not found.
    """

    directory: Path
    reason: str

    def __init__(self, directory: Path, reason: str) -> None:
        """Record where the search ran and what failed."""
        self.directory = directory
        self.reason = reason
        super().__init__(f"no application project at {directory}: {reason}")

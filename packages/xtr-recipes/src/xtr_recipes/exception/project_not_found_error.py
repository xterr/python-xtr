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
    searched; when not exactly one package under ``src/`` or the project root
    holds a ``kernel.py`` — the file that marks the application package; and
    when ``pyproject.toml`` still carries a setting that once named that
    package and is no longer read, so the owner deletes it rather than
    believing it still applies.

    Attributes:
        directory: The directory that was searched.
        reason: What was looked for and not found.
        setting: The ``pyproject.toml`` setting at fault, or ``None`` when no
            setting is.
    """

    directory: Path
    reason: str
    setting: str | None

    def __init__(self, directory: Path, reason: str, setting: str | None = None) -> None:
        """Record where the search ran, what failed, and the setting to blame."""
        self.directory = directory
        self.reason = reason
        self.setting = setting
        message = f"no application project at {directory}: {reason}"
        if setting is not None:
            message = f"{message} (setting: {setting})"
        super().__init__(message)

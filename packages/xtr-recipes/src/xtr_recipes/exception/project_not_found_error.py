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

    Raised in two situations: no ``pyproject.toml`` lies at or above the
    directory searched, or the application import name — from
    ``[tool.xtr-recipes] app`` when set, otherwise ``[project].name``
    normalised — resolves to neither ``src/<app>/`` nor ``<app>/``. The
    setting that chose the name is named, so the fix is to correct that
    setting rather than to guess where the application lives.

    Attributes:
        directory: The directory that was searched.
        reason: What was looked for and not found.
        setting: The setting the application name came from, or ``None`` when
            no project file was found at all.
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
            message = f"{message} (from {setting})"
        super().__init__(message)

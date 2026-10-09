"""A project with no web entry point to serve, or one named that it does not have."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from .cli_error import CliError

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["WebEntryPointNotFoundError"]


@final
class WebEntryPointNotFoundError(CliError):
    """Nothing in the project can be served, or ``--entrypoint`` names nothing it has.

    Attributes:
        project_dir: The project searched.
        reason: What was looked for and not found.
    """

    project_dir: Path
    reason: str

    def __init__(self, project_dir: Path, reason: str) -> None:
        """Record the project and what it lacks."""
        self.project_dir = project_dir
        self.reason = reason
        super().__init__(f"nothing to serve in {project_dir}: {reason}")

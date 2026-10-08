"""ScaffoldPlan: the files a new project gets and the commands that finish it."""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["ScaffoldPlan"]


@final
@dataclass(frozen=True, slots=True)
class ScaffoldPlan:
    """A project worked out in full and not yet made.

    Planning everything first means a dry run and a real one share one code
    path, and a template that cannot be rendered fails before the directory is
    touched.

    Attributes:
        directory: Where the project is made.
        files: Each path in the project, ``/``-separated, with the text written there.
        commands: The commands run in the project once its files are written, in order.
        next_steps: What to try once it is made.
    """

    directory: Path
    files: tuple[tuple[str, str], ...]
    commands: tuple[tuple[str, ...], ...]
    next_steps: tuple[str, ...]

    def render(self) -> tuple[str, ...]:
        """Return the plan as the lines a dry run prints: one per file, one per command."""
        return (
            *(f"write {path}" for path, _ in self.files),
            *(f"run   {shlex.join(argv)}" for argv in self.commands),
        )

"""WriteFile: putting a rendered template where the recipe says it goes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, final

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["WriteFile"]


@final
@dataclass(frozen=True, slots=True)
class WriteFile:
    """Writes one file, creating the directories above it.

    Used both for a file the project does not have yet and for one the sync
    owns and may overwrite; which of the two it is was decided when the plan
    was computed, so applying it is unconditional.

    Attributes:
        path: Where the file goes.
        display: How the path reads in the plan — relative to the project
            directory, ``/``-separated.
        content: The rendered text to write.
    """

    changes: ClassVar[bool] = True

    path: Path
    display: str
    content: str

    def render(self) -> tuple[str, ...]:
        """Return the line naming the file being written."""
        return (f"  write {self.display}",)

    def apply(self) -> None:
        """Write the content, creating the parent directories first."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        _ = self.path.write_text(self.content, encoding="utf-8")

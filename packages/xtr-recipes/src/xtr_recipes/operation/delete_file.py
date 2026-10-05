"""DeleteFile: taking back a file the recipe wrote and nobody touched."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, final

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["DeleteFile"]


@final
@dataclass(frozen=True, slots=True)
class DeleteFile:
    """Deletes one file the lock records as written and untouched since.

    Only reached for a file whose hash still matches the lock and that was not
    adopted, so nothing of the application owner's is at stake; an edited or
    adopted file is kept and reported instead.

    Attributes:
        path: The file to delete.
        display: How the path reads in the plan.
    """

    changes: ClassVar[bool] = True

    path: Path
    display: str

    def render(self) -> tuple[str, ...]:
        """Return the line naming the file being deleted."""
        return (f"  delete {self.display}",)

    def apply(self) -> None:
        """Delete the file; a file already gone is nothing to undo."""
        self.path.unlink(missing_ok=True)

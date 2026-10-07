"""DeleteProjectFile: taking back a generated file the run has nothing left to put in."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, final

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["DeleteProjectFile"]


@final
@dataclass(frozen=True, slots=True)
class DeleteProjectFile:
    """Deletes one of the files the whole run writes, once it would come out empty.

    The bundle list and the lock belong to the plan rather than to any one
    package — no bundle left to list, no recipe left to lock — so this stands
    in for the write that would have been and reads the same way: unindented,
    outside every package's block.

    Attributes:
        path: The file to delete.
        display: How the path reads in the plan.
    """

    changes: ClassVar[bool] = True

    path: Path
    display: str

    def render(self) -> tuple[str, ...]:
        """Return the line naming the file being deleted."""
        return (f"delete {self.display}",)

    def apply(self) -> None:
        """Delete the file; a file already gone is nothing to undo."""
        self.path.unlink(missing_ok=True)

"""MoveFile: setting aside a file whose package is gone, so the application still loads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, final

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["MoveFile"]


@final
@dataclass(frozen=True, slots=True)
class MoveFile:
    """Renames one file a removed package's recipe wrote or adopted.

    The file configures the package that was just removed, so left in place it
    would fail the next time the application scans it. It is the application
    owner's — edited, or there before the recipe — so it is not deleted either:
    renamed out of the way, it keeps every change and is imported by nothing.

    Attributes:
        path: The file to move.
        display: How its path reads in the plan.
        target: Where it goes, a name no import resolves to.
        target_display: How that path reads in the plan.
        reason: Why it was not simply deleted: ``"edited"`` or ``"adopted"``.
    """

    changes: ClassVar[bool] = True

    path: Path
    display: str
    target: Path
    target_display: str
    reason: str

    def render(self) -> tuple[str, ...]:
        """Return the line naming both paths and the reason."""
        return (f"  moved {self.display} to {self.target_display} ({self.reason})",)

    def apply(self) -> None:
        """Rename the file."""
        _ = self.path.rename(self.target)

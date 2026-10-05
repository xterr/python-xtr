"""WriteLock: committing what the sync just did, so it can be undone later."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, final

if TYPE_CHECKING:
    from pathlib import Path

    from xtr_recipes.recipe_lock import RecipeLock

__all__ = ["WriteLock"]

_DISPLAY = "xtr.lock"


@final
@dataclass(frozen=True, slots=True)
class WriteLock:
    """Writes ``xtr.lock``, the last step and the record of every other.

    The lock is what makes a recipe undoable once its package is gone, so it
    is written after the files, the blocks and the bundle list — and only when
    it differs from the one already committed, which is what lets a second
    sync be a plan of nothing.

    Attributes:
        lock: The lock to write.
        project_dir: The directory it goes in.
    """

    changes: ClassVar[bool] = True

    lock: RecipeLock
    project_dir: Path

    def render(self) -> tuple[str, ...]:
        """Return the line naming the lock being written."""
        return (f"write {_DISPLAY}",)

    def apply(self) -> None:
        """Write the lock into the project directory."""
        self.lock.write(self.project_dir)

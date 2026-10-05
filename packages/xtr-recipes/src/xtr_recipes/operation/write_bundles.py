"""WriteBundles: the one rewrite of the application's bundle list."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, final

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["WriteBundles"]


@final
@dataclass(frozen=True, slots=True)
class WriteBundles:
    """Writes the whole bundle list, once, after every package has had its say.

    The list is regenerated rather than patched, and every package in the plan
    contributes to the same file, so this is a step of the plan as a whole —
    unindented, like the lock — and it is left out entirely when the rendered
    file says what the file already says.

    Attributes:
        path: The ``bundles.py`` to write.
        display: How the path reads in the plan.
        content: The rendered file.
    """

    changes: ClassVar[bool] = True

    path: Path
    display: str
    content: str

    def render(self) -> tuple[str, ...]:
        """Return the line naming the bundle list being written."""
        return (f"write {self.display}",)

    def apply(self) -> None:
        """Write the rendered list, creating the directories above it."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        _ = self.path.write_text(self.content, encoding="utf-8")

"""RemoveBlock: taking back the lines one package owns in a shared file."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, final

from xtr_recipes.marked_block_editor import MarkedBlockEditor

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["RemoveBlock"]

_EDITOR = MarkedBlockEditor()


@final
@dataclass(frozen=True, slots=True)
class RemoveBlock:
    """Deletes the markers naming ``package`` and everything between them.

    The markers are what makes this safe: the block is removed whole rather
    than by guessing which lines were once written for the package, and a key
    the application owner set outside it is untouched.

    Attributes:
        path: The ``.env`` or ``.gitignore`` to edit.
        display: How the path reads in the plan.
        package: The distribution whose block goes away.
    """

    changes: ClassVar[bool] = True

    path: Path
    display: str
    package: str

    def render(self) -> tuple[str, ...]:
        """Return the line naming the file being cleared."""
        return (f"  clear {self.display}",)

    def apply(self) -> None:
        """Rewrite the file without this package's block."""
        text = _EDITOR.read(self.path)
        _EDITOR.write(self.path, _EDITOR.remove_block(text, self.package))

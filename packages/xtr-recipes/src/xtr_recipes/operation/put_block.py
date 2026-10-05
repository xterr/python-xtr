"""PutBlock: writing the lines one package owns in ``.env`` or ``.gitignore``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, final

from xtr_recipes.marked_block_editor import MarkedBlockEditor

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["PutBlock"]

_EDITOR = MarkedBlockEditor()


@final
@dataclass(frozen=True, slots=True)
class PutBlock:
    """Puts ``lines`` between the markers naming ``package`` in a shared file.

    An existing block is replaced where it stands, so applying the same recipe
    twice leaves the file byte for byte the same; everything outside the block
    is the application owner's and is never read for anything but deciding
    which lines are still missing.

    Attributes:
        path: The ``.env`` or ``.gitignore`` to edit.
        display: How the path reads in the plan.
        package: The distribution whose block this is.
        lines: What goes between the markers.
    """

    changes: ClassVar[bool] = True

    path: Path
    display: str
    package: str
    lines: tuple[str, ...]

    def render(self) -> tuple[str, ...]:
        """Return the line naming the file being written."""
        return (f"  write {self.display}",)

    def apply(self) -> None:
        """Rewrite the file with this package's block holding exactly these lines."""
        text = _EDITOR.read(self.path)
        _EDITOR.write(self.path, _EDITOR.put_block(text, self.package, self.lines))

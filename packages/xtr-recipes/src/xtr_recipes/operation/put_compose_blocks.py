"""PutComposeBlocks: writing the blocks one package owns in a Compose file."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, final

from xtr_recipes.compose_file_editor import ComposeFileEditor
from xtr_recipes.file_write import refuse_symlink, write_text

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

__all__ = ["PutComposeBlocks"]

_EDITOR = ComposeFileEditor()


@final
@dataclass(frozen=True, slots=True)
class PutComposeBlocks:
    """Puts ``package``'s blocks under the top-level keys of a Compose file.

    The file is read again when the step is applied, not when it was planned,
    so two recipes writing under ``services:`` in one run each add to what the
    other left. No sections clears the package's blocks; a file left with
    nothing in it is deleted, since a recipe is what made it.

    Attributes:
        path: The Compose file to edit.
        display: How the path reads in the plan.
        package: The distribution whose blocks these are.
        sections: Each top-level key mapped to the YAML lines under it.
    """

    changes: ClassVar[bool] = True

    path: Path
    display: str
    package: str
    sections: Mapping[str, tuple[str, ...]]

    def render(self) -> tuple[str, ...]:
        """Return the line naming the file being written or cleared."""
        verb = "write" if self.sections else "clear"
        return (f"  {verb} {self.display}",)

    def apply(self) -> None:
        """Rewrite the file with exactly this package's blocks, or delete it when left empty."""
        text = self.path.read_text(encoding="utf-8") if self.path.is_file() else ""
        written = _EDITOR.put_blocks(text, self.package, self.sections)
        if written:
            write_text(self.path, written)
        elif self.path.is_file():
            refuse_symlink(self.path)
            self.path.unlink()

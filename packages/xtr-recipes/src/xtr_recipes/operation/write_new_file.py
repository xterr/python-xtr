"""WriteNewFile: offering fresh content beside a file someone has edited."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, final

from xtr_recipes.file_write import write_text

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["WriteNewFile"]

_SUFFIX = ".new"


@final
@dataclass(frozen=True, slots=True)
class WriteNewFile:
    """Writes the rendered content to ``<path>.new``, leaving ``path`` alone.

    A file the application owner has edited, or one that was already there
    when the recipe first ran, is never overwritten: the new version is put
    beside it and reported, for the two to be reconciled by hand. There is no
    three-way merge. The planner emits this step only when ``<path>.new`` does
    not already hold the content, so a second sync has nothing to do here.

    Attributes:
        path: The file that is being left as it is.
        display: How that path reads in the plan; the ``.new`` is added when
            the line is rendered.
        content: The rendered text the recipe would write.
    """

    changes: ClassVar[bool] = True

    path: Path
    display: str
    content: str

    def render(self) -> tuple[str, ...]:
        """Return the line naming the ``.new`` file being written."""
        return (f"  write {self.display}{_SUFFIX}",)

    def apply(self) -> None:
        """Write the content beside the file, under the ``.new`` suffix."""
        write_text(self.path.parent / f"{self.path.name}{_SUFFIX}", self.content)

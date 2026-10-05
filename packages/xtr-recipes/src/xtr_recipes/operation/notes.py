"""Notes: the part of a recipe that is told to a person rather than written."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, final

__all__ = ["Notes"]


@final
@dataclass(frozen=True, slots=True)
class Notes:
    """Prints the manual steps, checks and commands a recipe cannot do itself.

    A recipe is declarative, so three things remain for someone to act on: a
    change to application code, a command that shows the package working, and
    a command that puts it to work. They are reported after the package's own
    steps and never written to disk.

    Attributes:
        steps: Manual changes the recipe cannot make.
        check: Commands that show the package working.
        run: Commands that put the package to work.
    """

    changes: ClassVar[bool] = False

    steps: tuple[str, ...] = ()
    check: tuple[str, ...] = ()
    run: tuple[str, ...] = ()

    def render(self) -> tuple[str, ...]:
        """Return a labelled group of lines per non-empty list, in order."""
        lines: list[str] = []
        for label, items in (("steps", self.steps), ("check", self.check), ("run", self.run)):
            if items:
                lines.append(f"  {label}:")
                lines.extend(f"    - {item}" for item in items)
        return tuple(lines)

    def apply(self) -> None:
        """Do nothing: notes are for a person, not for the project."""

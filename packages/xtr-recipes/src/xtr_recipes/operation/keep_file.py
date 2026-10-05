"""KeepFile: saying a file was left exactly as it is, and why."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, final

__all__ = ["KeepFile"]


@final
@dataclass(frozen=True, slots=True)
class KeepFile:
    """Reports a file the sync deliberately did not touch.

    Two things earn this: a file the application owner has edited since the
    recipe wrote it, and a file that was already there when the recipe first
    ran. Either way the content is theirs, so it is reported rather than
    changed — this step writes nothing.

    Attributes:
        display: How the path reads in the plan.
        reason: Why it was kept — ``edited`` or ``adopted``.
    """

    changes: ClassVar[bool] = False

    display: str
    reason: str

    def render(self) -> tuple[str, ...]:
        """Return the line naming the file and why it stands."""
        return (f"  kept {self.display} ({self.reason})",)

    def apply(self) -> None:
        """Do nothing: keeping a file is the absence of an action."""

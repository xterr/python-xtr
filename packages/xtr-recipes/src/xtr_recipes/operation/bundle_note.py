"""BundleNote: what became of one bundle a recipe brings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, final

__all__ = ["BundleNote"]


@final
@dataclass(frozen=True, slots=True)
class BundleNote:
    """Reports one bundle's standing in the application's list.

    The list itself is written once for the whole plan, so a per-package step
    cannot be the one doing it. This says what happened to a single bundle —
    newly listed, already there, left out because another bundle requires it,
    removed, or skipped for want of the extra that ships its class — and
    writes nothing.

    Attributes:
        class_name: The bundle class as the list spells it.
        note: What became of it.
    """

    changes: ClassVar[bool] = False

    class_name: str
    note: str

    def render(self) -> tuple[str, ...]:
        """Return the line naming the bundle and its standing."""
        return (f"  bundle {self.class_name} {self.note}",)

    def apply(self) -> None:
        """Do nothing: the bundle list is written by its own step."""

"""Plan: everything a sync would do, computed before any of it is done."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from .operation_interface import OperationInterface

__all__ = ["Plan"]


@final
@dataclass(frozen=True, slots=True)
class Plan:
    """The ordered steps of one sync, as data.

    Computing the whole plan before applying any of it is what makes printing
    it without doing it, and refusing a project that would change, the same
    code path as doing it: the steps are the single description both read.

    Attributes:
        operations: The steps, in the order they are reported and applied.
    """

    operations: tuple[OperationInterface, ...] = ()

    @property
    def has_changes(self) -> bool:
        """Whether any step would touch the project.

        A plan can be made entirely of headings, kept files and bundle notes —
        there is something to say and nothing to do. That is the difference
        between a sync that reports and one that writes.
        """
        return any(operation.changes for operation in self.operations)

    def render(self) -> tuple[str, ...]:
        """Return every step's lines, in order."""
        return tuple(line for operation in self.operations for line in operation.render())

    def apply(self) -> None:
        """Carry out every step, in order."""
        for operation in self.operations:
            operation.apply()

"""PlannedRecipe: one recipe's share of a plan, with what the lock must record."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, final

from .recipe_lock import LockedFile

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .operation.notes import Notes
    from .operation.operation_interface import OperationInterface

__all__ = ["PlannedRecipe"]


@final
@dataclass(frozen=True, slots=True)
class PlannedRecipe:
    """What one recipe contributes to a plan, and what it would then be locked as.

    The two travel together because they are decided together: whether a file
    is written or kept is the same judgement as whether the lock records the
    new hash or the old one. Bundles are absent — they are settled once for
    the whole plan, after every recipe has named its candidates.

    Attributes:
        operations: The recipe's own steps, in order: files first, then the
            shared ``.env`` and ``.gitignore`` blocks.
        notes: What to print after the steps, or ``None`` when the recipe has
            nothing to say.
        files: Each written path, as the lock spells it, mapped to what the
            lock should record for it.
        env: The environment keys the recipe wrote inside its own block.
        gitignore: The ignore lines it wrote inside its own block.
    """

    operations: tuple[OperationInterface, ...] = ()
    notes: Notes | None = None
    files: Mapping[str, LockedFile] = field(default_factory=dict[str, LockedFile])
    env: tuple[str, ...] = ()
    gitignore: tuple[str, ...] = ()

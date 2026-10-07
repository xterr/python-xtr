"""A path a recipe would write to or read from that is not safe to touch."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from .recipes_error import RecipesError

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["UnsafePathError"]


@final
class UnsafePathError(RecipesError):
    """A recipe path escapes the project or points at a symbolic link.

    A recipe records and resolves paths relative to the project directory, so
    one that resolves outside it — through ``..`` or an absolute spelling, in a
    manifest or in a tampered ``xtr.lock`` — would let a recipe write or delete
    anywhere on disk. A write target that is a symbolic link would follow the
    link out of the project just the same. Both are refused before anything is
    touched.

    Attributes:
        path: The path that could not be made safe, as it reads in the plan or
            the lock.
        reason: Why it was refused.
    """

    path: str
    reason: str

    def __init__(self, path: Path | str, reason: str) -> None:
        """Record the offending path and why it was refused."""
        self.path = str(path)
        self.reason = reason
        super().__init__(f"{self.path}: {reason}")

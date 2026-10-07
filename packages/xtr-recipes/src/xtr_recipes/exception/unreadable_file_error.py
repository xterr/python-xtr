"""A project file whose bytes could not be decoded into what was expected."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from .recipes_error import RecipesError

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["UnreadableFileError"]


@final
class UnreadableFileError(RecipesError):
    """A file the tool must read holds bytes it cannot decode.

    Raised where ``xtr.lock`` or a ``pyproject.toml`` is read: a truncated
    JSON lock, a manifest that is not valid TOML, or either saved in an
    encoding other than UTF-8 would otherwise surface as a bare decode error
    with no hint which file was at fault. The file is named so the fix is
    obvious.

    Attributes:
        path: The file that could not be read.
        reason: What about its bytes could not be decoded.
    """

    path: Path
    reason: str

    def __init__(self, path: Path, reason: str) -> None:
        """Record which file could not be read, and why."""
        self.path = path
        self.reason = reason
        super().__init__(f"{path}: {reason}")

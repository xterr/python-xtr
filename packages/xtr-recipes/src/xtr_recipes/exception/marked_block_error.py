"""A marked block in a project file that cannot be read back."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from .recipes_error import RecipesError

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["MarkedBlockError"]


@final
class MarkedBlockError(RecipesError, ValueError):
    """A recipe's block is opened in a file and never closed.

    The markers are the whole reason a recipe can be undone: everything between
    them belongs to the recipe, everything outside belongs to the application
    owner. An opening marker with no closing one leaves that line undrawn, and
    rewriting or removing the block would then swallow whatever follows it — so
    the file is reported rather than guessed at.

    Also a :class:`ValueError`, so code that already guards parsing with
    ``except ValueError`` keeps working without learning a new exception.

    Attributes:
        path_or_name: The file whose block is unclosed, or the package the
            block belongs to when the text was handed over without a path.
        reason: What about the block could not be read.
    """

    path_or_name: Path | str
    reason: str

    def __init__(self, path_or_name: Path | str, reason: str) -> None:
        """Record which file or package, and why its block could not be read."""
        self.path_or_name = path_or_name
        self.reason = reason
        super().__init__(f"{path_or_name}: {reason}")

"""The application's bundle list cannot be rewritten safely."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from .recipes_error import RecipesError

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["BundlesNotEditableError"]


@final
class BundlesNotEditableError(RecipesError):
    """A ``bundles.py`` is shaped in a way its reader cannot edit in place.

    The bundle list is read and rewritten mechanically; a file that builds its
    mapping some other way — a key that is not an imported name, non-literal
    flags, or no single ``BUNDLES`` assignment — cannot be changed without
    risking what it already holds. Rather than guess, the error reports the
    entries to add by hand so the application owner stays in control.

    Attributes:
        path: The ``bundles.py`` that could not be rewritten.
        reason: Why it could not be rewritten.
        entries: The bundle targets (``"module:Class"``) to add by hand.
    """

    path: Path
    reason: str
    entries: tuple[str, ...]

    def __init__(self, path: Path, reason: str, entries: tuple[str, ...]) -> None:
        """Record the file, why it is not editable, and what to add by hand."""
        self.path = path
        self.reason = reason
        self.entries = entries
        message = f"{path} cannot be rewritten: {reason}"
        if entries:
            message = f"{message}; add to BUNDLES by hand: {', '.join(entries)}"
        super().__init__(message)

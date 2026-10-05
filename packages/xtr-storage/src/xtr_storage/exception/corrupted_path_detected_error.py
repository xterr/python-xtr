"""A path carried characters no path may carry."""

from __future__ import annotations

from .storage_error import StorageError

__all__ = ["CorruptedPathDetectedError"]


class CorruptedPathDetectedError(StorageError):
    """A path held a control or formatting character.

    Anything Unicode files under "other" — a null byte, an escape, a
    zero-width joiner — is refused rather than passed on. Such a character
    survives a comparison but not a filesystem, a url or a log line, so a path
    holding one means two names that look identical and are not.

    Attributes:
        path: The path that was refused, as the caller gave it.
    """

    path: str

    def __init__(self, path: str) -> None:
        """Record the path that cannot be used."""
        self.path = path
        super().__init__(f"corrupted path detected in {path!r}")

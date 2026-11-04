"""Names the MIME type of a file on disk."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["MimeTypeGuesserInterface"]


@runtime_checkable
class MimeTypeGuesserInterface(Protocol):
    """Guesses the MIME type of the file at a path.

    A guesser may need something the host lacks — a native library, a command — so it tells
    whether it can run before it is asked, and :class:`~xtr_mime.MimeTypes` asks only the
    guessers that can.
    """

    def is_guesser_supported(self) -> bool:
        """Tell whether this guesser can run on this host."""
        ...

    def guess_mime_type(self, path: str) -> str | None:
        """Name the MIME type of the file at ``path``.

        Returns:
            The MIME type, or ``None`` when this guesser cannot tell.

        Raises:
            InvalidArgumentError: When ``path`` does not name a file this process may read.
            LogicError: When this guesser cannot run on this host.
        """
        ...

"""Something a message depends on failed while it was built or rendered."""

from __future__ import annotations

from .mime_error import MimeError

__all__ = ["MimeRuntimeError"]


class MimeRuntimeError(MimeError, RuntimeError):
    """Something outside the calling code failed: a file that vanished, a key that would not load.

    The values handed in were fine and so is the code; the world did not cooperate.
    """

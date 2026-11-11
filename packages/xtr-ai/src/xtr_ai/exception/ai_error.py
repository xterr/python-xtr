"""The root every error in this library derives from."""

from __future__ import annotations

__all__ = ["AiError"]


class AiError(Exception):
    """Base class for every error raised by this library.

    Catch this to handle anything the integration can go wrong with; catch a
    subclass to handle one cause. Each subclass carries what a caller needs as
    typed attributes and composes its own message from them.
    """

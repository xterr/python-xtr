"""The root every error in this library derives from."""

from __future__ import annotations

__all__ = ["WebProfilerError"]


class WebProfilerError(Exception):
    """Base class for every error raised by this library.

    Every subclass carries what went wrong as typed attributes and composes
    its own message from them.
    """

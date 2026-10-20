"""The error every other error of this package derives from."""

from __future__ import annotations

__all__ = ["NotifierError"]


class NotifierError(Exception):
    """Something a notification could not be sent through — catch this to catch them all."""

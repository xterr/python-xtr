"""Every error this library raises.

All of them derive from :class:`HttpFoundationError`, so one ``except`` catches anything
this library refuses, and a narrower one handles a single cause.
"""

from __future__ import annotations

from .http_foundation_error import HttpFoundationError
from .invalid_argument_error import InvalidArgumentError

__all__ = ["HttpFoundationError", "InvalidArgumentError"]

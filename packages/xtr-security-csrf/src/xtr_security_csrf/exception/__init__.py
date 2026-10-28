"""Every error this library raises.

All of them derive from :class:`CsrfError`, so one ``except`` catches
anything minting or checking a token can go wrong with, and a narrower one
handles a single cause. Each carries the data a caller needs as typed
attributes rather than forcing a message to be parsed.
"""

from __future__ import annotations

from .csrf_error import CsrfError
from .invalid_argument_error import InvalidArgumentError
from .token_not_found_error import TokenNotFoundError

__all__ = [
    "CsrfError",
    "InvalidArgumentError",
    "TokenNotFoundError",
]

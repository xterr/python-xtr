"""Every error this package raises, each deriving from :class:`RemoteEventError`."""

from __future__ import annotations

from .invalid_argument_error import InvalidArgumentError
from .logic_error import LogicError
from .parse_error import ParseError
from .remote_event_error import RemoteEventError

__all__ = [
    "InvalidArgumentError",
    "LogicError",
    "ParseError",
    "RemoteEventError",
]

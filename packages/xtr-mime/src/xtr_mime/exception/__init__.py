"""The errors this package raises, every one a :class:`MimeError`."""

from __future__ import annotations

from .invalid_argument_error import InvalidArgumentError
from .logic_error import LogicError
from .mime_error import MimeError
from .mime_runtime_error import MimeRuntimeError
from .rfc_compliance_error import RfcComplianceError

__all__ = [
    "InvalidArgumentError",
    "LogicError",
    "MimeError",
    "MimeRuntimeError",
    "RfcComplianceError",
]

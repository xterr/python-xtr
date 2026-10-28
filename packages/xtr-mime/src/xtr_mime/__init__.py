"""Email messages built in code and rendered to standard MIME.

A message is put together from addresses, headers, text and HTML bodies, attachments and
inline images; Python's own ``email`` package turns it into the bytes a mail server accepts,
and DKIM or S/MIME signs it when asked.
"""

from __future__ import annotations

from .address import Address
from .exception import (
    InvalidArgumentError,
    LogicError,
    MimeError,
    MimeRuntimeError,
    RfcComplianceError,
)
from .group import Group

__all__ = [
    "Address",
    "Group",
    "InvalidArgumentError",
    "LogicError",
    "MimeError",
    "MimeRuntimeError",
    "RfcComplianceError",
]

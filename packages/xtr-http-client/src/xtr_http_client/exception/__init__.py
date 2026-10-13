"""Everything calling out through this package can raise.

The hierarchy is the contract's, re-exported here so one import answers "what
can this client raise" without reaching into two packages: :class:`HttpClientError`
at the root, :class:`TransportError` for "there is no answer" (with
:class:`TransportTimeoutError` for running out of time), :class:`HttpError` for
"there is one and it is not a success" (:class:`RedirectionError`,
:class:`ClientError`, :class:`ServerError`), and :class:`DecodingError` for an
answer that is not what it was read as.

Two errors are this package's own, and both are narrower names for cases the
contract already covers: :class:`InvalidArgumentError` for a request this
client refuses to make, and :class:`JsonError` for a body that is not the JSON
it was read as.
"""

from __future__ import annotations

from xtr_http_client_contracts import (
    ClientError,
    DecodingError,
    HttpClientError,
    HttpError,
    RedirectionError,
    ServerError,
    TransportError,
    TransportTimeoutError,
)

from .invalid_argument_error import InvalidArgumentError
from .json_error import JsonError

__all__ = [
    "ClientError",
    "DecodingError",
    "HttpClientError",
    "HttpError",
    "InvalidArgumentError",
    "JsonError",
    "RedirectionError",
    "ServerError",
    "TransportError",
    "TransportTimeoutError",
]

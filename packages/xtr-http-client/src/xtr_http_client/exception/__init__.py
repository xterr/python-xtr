"""Everything calling out through this package can raise.

The hierarchy is the contract's, re-exported here so one import answers "what
can this client raise" without reaching into two packages: :class:`HttpClientError`
at the root, :class:`TransportError` for "there is no answer" (with
:class:`TransportTimeoutError` for running out of time), :class:`HttpError` for
"there is one and it is not a success" (:class:`RedirectionError`,
:class:`ClientError`, :class:`ServerError`), :class:`DecodingError` for an
answer that is not what it was read as (with :class:`JsonError` for a body that
is not the JSON it was read as), and :class:`InvalidArgumentError` for a request
this client refuses to make. :class:`LogicError` is this package's own: a client
built in a way that cannot work.
"""

from __future__ import annotations

from xtr_http_client_contracts import (
    ClientError,
    DecodingError,
    HttpClientError,
    HttpError,
    InvalidArgumentError,
    JsonError,
    RedirectionError,
    ServerError,
    TransportError,
    TransportTimeoutError,
)

from .logic_error import LogicError

__all__ = [
    "ClientError",
    "DecodingError",
    "HttpClientError",
    "HttpError",
    "InvalidArgumentError",
    "JsonError",
    "LogicError",
    "RedirectionError",
    "ServerError",
    "TransportError",
    "TransportTimeoutError",
]

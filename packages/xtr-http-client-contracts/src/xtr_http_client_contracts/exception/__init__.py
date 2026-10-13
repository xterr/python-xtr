"""The errors the HTTP client contract names.

:class:`HttpClientError` is the root every one of them derives from,
including every error an implementation adds, so catching it catches anything
calling out can go wrong with, whichever client raised it.

Below it, two branches that mean different things. A
:class:`TransportError` — with :class:`TransportTimeoutError` for running out
of time — says there is no answer to look at. An :class:`HttpError` says
there is one and it is not a success: :class:`RedirectionError` for a 3xx
nobody followed, :class:`ClientError` for a 4xx, :class:`ServerError` for a
5xx, each carrying the response. :class:`DecodingError` is the third case:
the answer arrived whole and is not what it was being read as.
"""

from __future__ import annotations

from .client_error import ClientError
from .decoding_error import DecodingError
from .http_client_error import HttpClientError
from .http_error import HttpError
from .invalid_argument_error import InvalidArgumentError
from .json_error import JsonError
from .redirection_error import RedirectionError
from .server_error import ServerError
from .transport_error import TransportError
from .transport_timeout_error import TransportTimeoutError

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

"""The async HTTP client contract: what code that calls out depends on, and nothing more.

A library that sends an HTTP request should not decide what sends it. It takes the client
interface, asks for a method and a URL — or hands over a message request — and gets back a
response whose status line and headers have arrived, its body read when, and only when, the
caller wants it.

What is here is only what appears in that contract: the client, the response it answers with,
the options a request takes, the errors any of them raises, and a conformance suite an
implementation can run against itself.
"""

from __future__ import annotations

from .exception import (
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
from .http_client_interface import HttpClientInterface
from .http_response_interface import HttpResponseInterface
from .options_defaults import OPTIONS_DEFAULTS
from .request_options import RequestOptions

__all__ = [
    "OPTIONS_DEFAULTS",
    "ClientError",
    "DecodingError",
    "HttpClientError",
    "HttpClientInterface",
    "HttpError",
    "HttpResponseInterface",
    "InvalidArgumentError",
    "JsonError",
    "RedirectionError",
    "RequestOptions",
    "ServerError",
    "TransportError",
    "TransportTimeoutError",
]

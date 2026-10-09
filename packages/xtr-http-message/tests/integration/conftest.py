"""The subjects the conformance suite is run against.

The harness asks an implementation for its subjects through a handful of hooks
— one per kind of message — and runs every scenario against whatever comes
back. Here those hooks are fixtures, each building one of this package's six
classes.

Two of them hand out more than one kind: every scenario about a message runs
against a request, a response and a server request, and every scenario about a
request runs against both kinds of request, which is how the harness nests its
suites.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Final, cast

import pytest

from xtr_http_message.factory.http_factory import HttpFactory
from xtr_http_message.request import Request
from xtr_http_message.response import Response
from xtr_http_message.server_request import ServerRequest
from xtr_http_message.stream import Stream

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from xtr_http_message_contracts import (
        MessageInterface,
        RequestInterface,
        ResponseInterface,
        ServerRequestInterface,
        UploadedFileInterface,
    )

# The harness reads the environment a request arrived in off a process-wide
# table the language keeps; nothing of the sort exists here, so the suite hands
# the constructor what it expects to read back.
SERVER_PARAMS: Final[Mapping[str, object]] = MappingProxyType({"REQUEST_METHOD": "GET"})

# What the harness uploads: a stream over a short payload, wrapped by the
# factory so that the size is counted the way an application would get it.
UPLOADED_PAYLOAD: Final[bytes] = b"writing to tempfile"


def build_request() -> RequestInterface:
    """Return the outgoing request the suite starts every request scenario from."""
    return Request("GET", "/")


def build_response() -> ResponseInterface:
    """Return the response the suite starts every response scenario from."""
    return Response()


def build_server_request() -> ServerRequestInterface:
    """Return the incoming request the suite starts every server scenario from."""
    return ServerRequest("GET", "/", None, None, "1.1", SERVER_PARAMS)


def build_uploaded_file() -> UploadedFileInterface:
    """Return the uploaded file the suite starts every upload scenario from."""
    return HttpFactory().create_uploaded_file(Stream.create(UPLOADED_PAYLOAD))


_MESSAGES: Final[Mapping[str, Callable[[], MessageInterface]]] = MappingProxyType(
    {
        "request": build_request,
        "response": build_response,
        "server_request": build_server_request,
    }
)

_REQUESTS: Final[Mapping[str, Callable[[], RequestInterface]]] = MappingProxyType(
    {
        "request": build_request,
        "server_request": build_server_request,
    }
)


@pytest.fixture(params=list(_MESSAGES))
def message(request: pytest.FixtureRequest) -> MessageInterface:
    """Return a fresh message of each kind this package implements."""
    return _MESSAGES[cast("str", request.param)]()


@pytest.fixture(params=list(_REQUESTS))
def request_subject(request: pytest.FixtureRequest) -> RequestInterface:
    """Return a fresh request of each kind this package implements."""
    return _REQUESTS[cast("str", request.param)]()


@pytest.fixture
def response() -> ResponseInterface:
    """Return a fresh response."""
    return build_response()


@pytest.fixture
def server_request() -> ServerRequestInterface:
    """Return a fresh incoming request."""
    return build_server_request()


@pytest.fixture
def server_params() -> Mapping[str, object]:
    """Return the environment every incoming request in the suite is built with."""
    return SERVER_PARAMS


@pytest.fixture
def uploaded_file() -> UploadedFileInterface:
    """Return a fresh uploaded file that arrived whole."""
    return build_uploaded_file()

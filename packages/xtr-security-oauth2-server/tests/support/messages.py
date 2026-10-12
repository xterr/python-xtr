"""Building the messages the library is handed, and reading the answers back.

The library speaks the HTTP message contracts, so every test that exercises it
needs a request and a response that satisfy them. The implementation builds
both, but it builds a request the way a server does — the query out of the URI,
the body and the attributes added afterwards — while a test wants to say in one
place what the request carries. That is what :func:`server_request` is for.

:func:`body_of` is the other half: a response body is a stream of bytes, and a
test asserting on a document wants the text.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

from xtr_http_message import ServerRequest

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface

__all__ = ["body_of", "document_of", "server_request"]


def server_request(
    method: str = "POST",
    uri: str = "/token",
    *,
    headers: Mapping[str, str | Sequence[str]] | None = None,
    parsed_body: object | None = None,
    query_params: Mapping[str, object] | None = None,
    cookie_params: Mapping[str, str] | None = None,
    server_params: Mapping[str, object] | None = None,
    attributes: Mapping[str, object] | None = None,
) -> ServerRequestInterface:
    """Return a request carrying everything named, as one expression.

    The query parameters are set rather than parsed out of ``uri`` when they
    are named, so a test says what the request asks for without having to
    spell a query string; left out, they are whatever ``uri`` carries, as they
    would be for a request that really arrived.
    """
    request: ServerRequestInterface = ServerRequest(
        method,
        uri,
        headers,
        None,
        "1.1",
        server_params,
    )
    if parsed_body is not None:
        request = request.with_parsed_body(parsed_body)
    if query_params is not None:
        request = request.with_query_params(query_params)
    if cookie_params is not None:
        request = request.with_cookie_params(cookie_params)
    for name, value in (attributes or {}).items():
        request = request.with_attribute(name, value)

    return request


def body_of(response: ResponseInterface) -> str:
    """Return the body of ``response`` as the text it was written as."""
    return bytes(response.get_body()).decode()


def document_of(response: ResponseInterface) -> object:
    """Return the JSON document ``response`` carries, read back."""
    return cast("object", json.loads(body_of(response)))

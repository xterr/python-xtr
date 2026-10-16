"""Building a request message for the HTTP-edge tests.

Everything the security layer reads — the matchers a firewall matches with,
the extractors a token is read by, the entry points and handlers a failure is
answered by — takes the request as a message, so a test that exercises one
builds it here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_http_message import ServerRequest

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["make_message"]


def make_message(  # noqa: PLR0913 -- a test builder, naming every part of a request it can shape
    *,
    method: str = "GET",
    path: str = "/",
    host: str = "example.com",
    client: tuple[str, int] | None = None,
    query: str = "",
    headers: Mapping[str, str] | None = None,
    body: bytes | None = None,
    parsed_body: object | None = None,
) -> ServerRequest:
    """Return a request message with the given method, path, host, client and body.

    The client is the address the server accepted the connection from, as the
    server reports it: the address first, then the port. Extra environment
    parameters ride along under ``server_params``.

    The parsed body is what a served request would answer once its body had
    been read: a test that wants a form's fields without reading the wire
    sets them here, the same way the kernel's materialisation would.
    """
    asked = f"?{query}" if query else ""
    uri = f"https://{host}{path}{asked}"
    params = None if client is None else {"client": client}
    message = ServerRequest(method, uri, dict(headers or {}), body, server_params=params)
    if parsed_body is not None:
        message = message.with_parsed_body(parsed_body)
    return message

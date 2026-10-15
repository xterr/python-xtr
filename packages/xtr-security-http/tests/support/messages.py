"""Building a request message for the HTTP-edge tests.

The matchers a firewall matches with read a request as a message, so a test
that exercises one builds it here. The framework's own request object — still
what authentication reads and what the firewall memoises on — is built by
:mod:`tests.support.requests`.
"""

from __future__ import annotations

from xtr_http_message import ServerRequest

__all__ = ["make_message"]


def make_message(
    *,
    method: str = "GET",
    path: str = "/",
    host: str = "example.com",
    client: tuple[str, int] | None = None,
    query: str = "",
) -> ServerRequest:
    """Return a request message with the given method, path, host and client.

    The client is the address the server accepted the connection from, as the
    server reports it: the address first, then the port. Extra environment
    parameters ride along under ``server_params``.
    """
    asked = f"?{query}" if query else ""
    uri = f"https://{host}{path}{asked}"
    params = None if client is None else {"client": client}
    return ServerRequest(method, uri, server_params=params)

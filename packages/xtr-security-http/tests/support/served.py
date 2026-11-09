"""Serving a request the way the kernel does, for the tests of what the chain reads.

The lifecycle hands the chain a request born connected to its wire: the head
read at once, the body left lazy until something reads it. A test of what the
chain reads out of a body builds the request here, over a channel that counts
how often the wire was read, so it can tell what was read and what was not —
or sends one straight at an application, the way a server would.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

from starlette.requests import Request
from xtr_http_kernel.bridge import HttpMessageFactory, ResponseFactory
from xtr_http_message import HttpFactory

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Message, Scope
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["BodyChannel", "http_scope", "message_factory", "send", "served_message"]


def message_factory() -> HttpMessageFactory:
    """Return the bridge's message factory, built by hand as the middleware's is."""
    one = HttpFactory()
    return HttpMessageFactory(one, one, one, ResponseFactory(), one)


def http_scope(
    method: str,
    path: str,
    *,
    query: str = "",
    content_type: str | None = None,
) -> Scope:
    """Return the connection a server describes for one request to ``path``."""
    headers = [(b"host", b"example.com")]
    if content_type is not None:
        headers.append((b"content-type", content_type.encode()))
    return {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "https",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": query.encode(),
        "headers": headers,
        "client": ("127.0.0.1", 50000),
        "server": ("example.com", 443),
    }


@final
class BodyChannel:
    """The channel a request's body arrives on, counting how often it was read."""

    def __init__(self, body: bytes) -> None:
        """Hold ``body``, handed out in one message on the first read."""
        self._body = body
        self.reads = 0

    async def __call__(self) -> Message:
        """Hand out the body once, then the disconnect."""
        self.reads += 1
        if self.reads == 1:
            return {"type": "http.request", "body": self._body, "more_body": False}
        return {"type": "http.disconnect"}


def served_message(
    method: str,
    path: str,
    body: bytes = b"",
    *,
    content_type: str | None = None,
) -> tuple[ServerRequestInterface, BodyChannel]:
    """Return a request served the kernel's way, with the channel its body arrives on."""
    channel = BodyChannel(body)
    request = Request(http_scope(method, path, content_type=content_type), channel)
    return message_factory().serve(request), channel


async def send(  # noqa: PLR0913 -- a test client, naming every part of the request it sends
    app: ASGIApp,
    method: str,
    path: str,
    body: bytes = b"",
    *,
    query: str = "",
    content_type: str | None = None,
) -> tuple[int, dict[str, str], bytes]:
    """Send one request straight at ``app``, answering its status, headers and body."""
    sent: list[Message] = []

    async def collect(message: Message) -> None:
        sent.append(message)

    scope = http_scope(method, path, query=query, content_type=content_type)
    await app(scope, BodyChannel(body), collect)
    start = sent[0]
    headers = {
        name.decode(): value.decode()
        for name, value in cast("list[tuple[bytes, bytes]]", start["headers"])
    }
    content = b"".join(
        cast("bytes", message.get("body", b""))
        for message in sent
        if message["type"] == "http.response.body"
    )
    return cast("int", start["status"]), headers, content

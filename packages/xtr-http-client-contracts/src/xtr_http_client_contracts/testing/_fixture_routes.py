"""What the fixture server answers, route by route.

Each route exists to put a client in one awkward position: a redirect it must follow or refuse,
a length that does not match the body, a body compressed only in name, a transfer that never
ends. ``_fixture_response`` holds how any of it reaches the wire.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Final
from urllib.parse import parse_qsl

from ._fixture_response import Answer, compact, compressed, head, length, pretty, send

if TYPE_CHECKING:
    from asyncio import StreamWriter
    from collections.abc import Awaitable, Callable, Mapping
    from typing import TypeAlias

    from ._fixture_request import FixtureRequest

    _Route: TypeAlias = Callable[[FixtureRequest, StreamWriter], Awaitable[None]]

__all__ = ["respond"]

# The standard library's decoder answers anything at all; saying here what this module asks
# of it keeps that looseness to one line, guarded by the check in `_json_fields`.
_decode_object: Final[Callable[[bytes], dict[str, object]]] = json.loads

_JSON: Final = ("Content-Type", "application/json")
_HTML: Final = ("Content-Type", "text/html; charset=UTF-8")
_TEXT: Final = ("Content-Type", "text/plain")
_ETAG: Final = ("ETag", '"abc123"')
_EXPECTED_BASIC: Final = "Basic Zm9vOmJhcg=="
_HEAD_DELAY: Final = 0.3
_BODY_DELAY: Final = 0.5
_HINT_DELAY: Final = 0.001
_SILENCE: Final = 1.0
_TICK: Final = 0.0005

# The hints and the answer after them are written verbatim: an interim response is not
# something a client library can be asked to produce, so the test server hands over the bytes.
_EARLY_HINTS: Final = (
    b"HTTP/1.1 103 Early Hints\r\n"
    b"Link: </style.css>; rel=preload; as=style\r\n"
    b"Link: </script.js>; rel=preload; as=script\r\n"
    b"\r\n"
)
_AFTER_HINTS: Final = (
    b"HTTP/1.1 200 OK\r\n"
    b"Date: Fri, 26 May 2017 10:02:11 GMT\r\n"
    b"Content-Length: 13\r\n"
    b"\r\n"
    b"Here the body"
)
_CHUNKS: Final = b"8\r\nchunked \r\n5\r\ndata \r\n6\r\nworks!\r\n0\r\n\r\n"
_TRUNCATED_CHUNKS: Final = b"8\r\nchunked \r\n5\r\ndata \r\n6\r\nw"
_NOT_GZIP: Final = b"-" * 1000
_DOCUMENTS: Final = {"documents": [{"id": "/json/1"}, {"id": "/json/2"}, {"id": "/json/3"}]}


def _echoing(status: int, *headers: tuple[str, str]) -> _Route:
    """A route answering ``status``, ``headers`` and the request's own variables as JSON."""

    async def route(request: FixtureRequest, writer: StreamWriter) -> None:
        body = pretty(request.variables())
        answer = Answer(status, (*headers, _JSON, length(body)))
        await send(writer, head(request, answer), body)

    return route


_PLAIN: Final[_Route] = _echoing(200)
_MOVED: Final[_Route] = _echoing(301, ("Location", "http://127.0.0.1:8057/302"))
_TAGGED: Final[_Route] = _echoing(200, _ETAG)


async def _nothing(request: FixtureRequest, writer: StreamWriter) -> None:
    """An unrouted path answers an empty 200, so a client sees a valid, useless response."""
    await send(writer, head(request, Answer(200, (_HTML, ("Content-Length", "0")))))


async def _root(request: FixtureRequest, writer: StreamWriter) -> None:
    """The variables, gzipped when the request asked for it."""
    body, encoding = compressed(request, pretty(request.variables()))
    answer = Answer(200, (*encoding, _JSON, length(body)))
    await send(writer, head(request, answer), body)


async def _withheld_body(request: FixtureRequest, writer: StreamWriter) -> None:
    """Declares the length of a body a HEAD request will not receive."""
    variables = request.variables()
    body = pretty(variables)
    headers = (("X-Request-Vars", compact(variables)), _JSON, length(body))
    await send(
        writer,
        head(request, Answer(200, headers)),
        b"" if request.method == "HEAD" else body,
    )


async def _early_hints(request: FixtureRequest, writer: StreamWriter) -> None:
    """Hints first, the answer after, so a client must keep reading past a 1xx."""
    del request
    await send(writer, _EARLY_HINTS)
    await asyncio.sleep(_HINT_DELAY)
    await send(writer, _AFTER_HINTS)


async def _gzipped_not_found(request: FixtureRequest, writer: StreamWriter) -> None:
    """A 404 whose head arrives long before its compressed body."""
    body, encoding = compressed(request, b"some text")
    await send(writer, head(request, Answer(404, (_TEXT, *encoding))))
    await asyncio.sleep(_HEAD_DELAY)
    await send(writer, body)


async def _credentialed_redirect(request: FixtureRequest, writer: StreamWriter) -> None:
    """Redirects only to a request carrying the credentials the fixture expects."""
    route = _MOVED if request.header("authorization") == _EXPECTED_BASIC else _PLAIN
    await route(request, writer)


async def _found(request: FixtureRequest, writer: StreamWriter) -> None:
    """Redirects until a request arrives with credentials, which ends the chain."""
    if request.header("authorization") is not None:
        await _PLAIN(request, writer)
        return
    targets = [value for name, value in _parameters(request) if name == "location"]
    location = targets[-1] if targets else "http://localhost:8057/"
    await _echoing(302, ("Location", location))(request, writer)


async def _not_modified(request: FixtureRequest, writer: StreamWriter) -> None:
    """Declares ten bytes and sends five, under a status allowed no body at all."""
    await send(writer, head(request, Answer(304, (("Content-Length", "10"),))), b"12345")


async def _etag_route(request: FixtureRequest, writer: StreamWriter) -> None:
    """Answers the variables, or nothing at all to a request that already has them."""
    if request.header("if-none-match") is None:
        await _TAGGED(request, writer)
        return
    await send(writer, head(request, Answer(304, (_ETAG,))))


async def _broken_length(request: FixtureRequest, writer: StreamWriter) -> None:
    """Declares a length the body never reaches, so a client waits for bytes that never come."""
    body = pretty(request.variables())
    answer = Answer(200, (("Content-Length", "1000"), _JSON))
    await send(writer, head(request, answer), body)


async def _echo_posted(request: FixtureRequest, writer: StreamWriter) -> None:
    """Answers what was sent: a form's fields, or a JSON body's keys and its content type."""
    body = pretty(_posted(request))
    answer = Answer(200, (_JSON, length(body)))
    await send(writer, head(request, answer), body)


async def _slow_head(request: FixtureRequest, writer: StreamWriter) -> None:
    """Says nothing at all for long enough to trip a timeout before the status arrives."""
    await asyncio.sleep(_HEAD_DELAY)
    await _PLAIN(request, writer)


async def _slow_body(request: FixtureRequest, writer: StreamWriter) -> None:
    """Answers, then pauses mid-body long enough to trip a timeout between chunks."""
    await send(writer, head(request, Answer(200, (_HTML,))), b"<1>")
    await asyncio.sleep(_BODY_DELAY)
    await send(writer, b"<2>")


async def _endless(request: FixtureRequest, writer: StreamWriter) -> None:
    """Writes until the client goes away, so only a deadline ends the transfer."""
    await send(writer, head(request, Answer(200, (_HTML,))), b"<1>")
    while not writer.is_closing():
        await asyncio.sleep(_TICK)
        await send(writer, b"<1>")


async def _silent_then_endless(request: FixtureRequest, writer: StreamWriter) -> None:
    """Silent for a second, then endless: a deadline may fall on either side of the status."""
    await asyncio.sleep(_SILENCE)
    await _endless(request, writer)


async def _chunked(request: FixtureRequest, writer: StreamWriter) -> None:
    """A body framed in three chunks, as a client reading chunk by chunk should see it."""
    answer = Answer(200, (_HTML, ("Transfer-Encoding", "chunked")))
    await send(writer, head(request, answer), _CHUNKS)


async def _chunked_broken(request: FixtureRequest, writer: StreamWriter) -> None:
    """Stops inside the third chunk, leaving the framing unfinished."""
    answer = Answer(200, (_HTML, ("Transfer-Encoding", "chunked")))
    await send(writer, head(request, answer), _TRUNCATED_CHUNKS)


async def _gzip_broken(request: FixtureRequest, writer: StreamWriter) -> None:
    """Announces gzip and sends something else, so decoding must fail, not the transfer."""
    answer = Answer(200, (_HTML, ("Content-Encoding", "gzip"), length(_NOT_GZIP)))
    await send(writer, head(request, answer), _NOT_GZIP)


async def _json_index(request: FixtureRequest, writer: StreamWriter) -> None:
    """Three document ids, for a client fetching them one after another."""
    body = compact(_DOCUMENTS).encode()
    await send(writer, head(request, Answer(200, (_JSON, length(body)))), body)


async def _json_document(request: FixtureRequest, writer: StreamWriter) -> None:
    """A document titled after the target it was asked for."""
    body = compact({"title": request.target}).encode()
    await send(writer, head(request, Answer(200, (_JSON, length(body)))), body)


async def _custom(request: FixtureRequest, writer: StreamWriter) -> None:
    """Answers the status and headers the query string asks for."""
    status = 200
    headers: list[tuple[str, str]] = []
    for name, value in _parameters(request):
        if name == "status" and value.isdigit():
            status = int(value)
        elif name == "headers[]":
            field, _, content = value.partition(":")
            # The echo sets its own content type last, so asking for another is pointless.
            if field.strip().lower() != "content-type":
                headers.append((field.strip(), content.strip()))
    await _echoing(status, *headers)(request, writer)


def _parameters(request: FixtureRequest) -> list[tuple[str, str]]:
    return parse_qsl(request.query, keep_blank_values=True)


def _posted(request: FixtureRequest) -> dict[str, object]:
    """The fields a request carried, named as the echo answers them.

    A form is answered as its fields. Anything else is read as JSON, and the content type is
    answered alongside its keys — ``?`` when the request named none, so a client can tell a
    missing header from an empty one. The method is answered last, unless a field claimed
    the name first.
    """
    fields = _form_fields(request)
    if not fields:
        fields = _json_fields(request.body)
        fields["content-type"] = request.header("content-type") or "?"
    if "REQUEST_METHOD" not in fields:
        fields["REQUEST_METHOD"] = request.method
    return fields


def _form_fields(request: FixtureRequest) -> dict[str, object]:
    content_type = request.header("content-type") or ""
    if request.method != "POST" or not content_type.startswith("application/x-www-form-urlencoded"):
        return {}
    return dict(parse_qsl(request.body.decode("latin-1")))


def _json_fields(body: bytes) -> dict[str, object]:
    """The keys of a JSON object body; anything else carries no fields to echo."""
    if not body.lstrip().startswith(b"{"):
        return {}
    try:
        return _decode_object(body)
    except ValueError:
        return {}


_ROUTES: Final[Mapping[str, _Route]] = {
    "/": _root,
    "/103": _early_hints,
    "/301": _credentialed_redirect,
    "/301/bad-tld": _echoing(301, ("Location", "http://foo.example.")),
    "/301/invalid": _echoing(301, ("Location", "//?foo=bar")),
    "/301/proxy": _echoing(301, ("Location", "http://localhost:8057/")),
    "/302": _found,
    "/302/relative": _echoing(302, ("Location", "..")),
    "/304": _not_modified,
    "/304/etag": _etag_route,
    "/307": _echoing(307, ("Location", "http://localhost:8057/post")),
    "/404": _echoing(404),
    "/404-gzipped": _gzipped_not_found,
    "/chunked": _chunked,
    "/chunked-broken": _chunked_broken,
    "/custom": _custom,
    "/gzip-broken": _gzip_broken,
    "/head": _withheld_body,
    "/json": _json_index,
    "/json/1": _json_document,
    "/json/2": _json_document,
    "/json/3": _json_document,
    "/length-broken": _broken_length,
    "/max-duration": _endless,
    "/post": _echo_posted,
    "/timeout-body": _slow_body,
    "/timeout-header": _slow_head,
    "/timeout-long": _silent_then_endless,
}


async def respond(request: FixtureRequest, writer: StreamWriter) -> None:
    """Answer ``request`` on ``writer``, dispatching on the target's path."""
    await _ROUTES.get(request.path, _nothing)(request, writer)

"""How the fixture server puts a response on the wire.

Responses are assembled as bytes rather than by a server framework: several routes answer
something deliberately malformed — a length that does not match the body, a declared encoding
the body does not use, framing that stops mid-chunk — and no framework would emit those.

Every response answers in the protocol its request came in with and closes the connection, so
a client never has to guess where a body that declares no length ends.
"""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from http import HTTPStatus
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from asyncio import StreamWriter
    from collections.abc import Mapping

    from ._fixture_request import FixtureRequest

__all__ = ["Answer", "compact", "compressed", "head", "length", "pretty", "send"]

_PHRASES = {status.value: status.phrase for status in HTTPStatus}


@final
@dataclass(frozen=True, slots=True)
class Answer:
    """A status and the headers to answer with; the body follows them."""

    status: int
    headers: tuple[tuple[str, str], ...] = ()


def head(request: FixtureRequest, answer: Answer) -> bytes:
    """The status line and headers, ending with the blank line that opens the body."""
    phrase = _PHRASES.get(answer.status, "Unknown")
    lines = [f"{request.protocol} {answer.status} {phrase}"]
    lines += [f"{name}: {value}" for name, value in answer.headers]
    lines.append("Connection: close")
    return ("\r\n".join(lines) + "\r\n\r\n").encode("latin-1")


async def send(writer: StreamWriter, *parts: bytes) -> None:
    """Write, and wait for it to leave: a client that hung up ends the route here."""
    writer.write(b"".join(parts))
    await writer.drain()


def pretty(payload: Mapping[str, object]) -> bytes:
    """JSON indented as the echo routes answer it."""
    return json.dumps(payload, indent=4, ensure_ascii=False).encode()


def compact(payload: Mapping[str, object]) -> str:
    """JSON with no spacing, for the payloads that travel in a header."""
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def length(body: bytes) -> tuple[str, str]:
    """The header declaring ``body``'s real length."""
    return ("Content-Length", str(len(body)))


def compressed(
    request: FixtureRequest,
    payload: bytes,
) -> tuple[bytes, tuple[tuple[str, str], ...]]:
    """``payload`` gzipped and the headers saying so, when the request asked for gzip.

    A request that did not ask gets the payload as it is, and no headers: a client must be
    able to drive the same route both ways.
    """
    if "gzip" not in (request.header("accept-encoding") or ""):
        return payload, ()
    return gzip.compress(payload), (("Content-Encoding", "gzip"), ("Vary", "Accept-Encoding"))

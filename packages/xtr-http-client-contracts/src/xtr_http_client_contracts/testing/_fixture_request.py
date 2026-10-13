"""One request the fixture server read, and the variables its echo routes answer with.

The echo routes answer a JSON object describing the request they received, so a client test can
assert on what actually arrived. The names in that object are:

======================  ====================================================================
``SERVER_PROTOCOL``     the protocol token the request came in with, e.g. ``HTTP/1.1``
``SERVER_NAME``         the host the server is bound to, not the one the request asked for
``REQUEST_URI``         the raw request target, absolute-form and query string included
``REQUEST_METHOD``      the method, as sent
``AUTH_USER``           the user of the request's Basic credentials, when it carried any
``AUTH_PW``             their password, split off at the first colon
``REMOTE_ADDR``         the address the connection came from
``REMOTE_PORT``         its port, as a string
``HTTP_<NAME>``         every request header, upper-cased, dashes turned into underscores
======================  ====================================================================

The order is the one above: the fixed names first, then the headers as they arrived. A header
sent more than once is answered once, its values joined with ``", "``. ``AUTH_USER`` and
``AUTH_PW`` appear only when the request carried credentials this module could decode — the
fixture these routes answer like exposed the same two values under names belonging to its own
runtime, which would mean nothing here.
"""

from __future__ import annotations

import asyncio
from base64 import b64decode
from dataclasses import dataclass
from typing import TYPE_CHECKING, final
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["FixtureRequest", "read_request"]

_REQUEST_LINE_PARTS = 3
_BASIC = "basic"


@final
@dataclass(frozen=True, slots=True)
class FixtureRequest:
    """What arrived on one connection, parsed no further than the routes need."""

    method: str
    target: str
    protocol: str
    headers: tuple[tuple[str, str], ...]
    body: bytes
    peer: tuple[str, str]
    server_name: str

    @property
    def path(self) -> str:
        """The target's path, which is what the routes dispatch on.

        An absolute target — what a client sends through a proxy — routes on its path too, so
        ``http://localhost:8057/301/proxy`` reaches the same route as ``/301/proxy``.
        """
        return urlsplit(self.target).path

    @property
    def query(self) -> str:
        """The target's query string, undecoded."""
        return urlsplit(self.target).query

    def header(self, name: str) -> str | None:
        """The named header, repeats joined, or ``None`` when it was not sent."""
        return _joined(self.headers, name)

    def credentials(self) -> tuple[str, str] | None:
        """The Basic user and password the request carried, or ``None``.

        Anything that is not a decodable ``Basic`` token holding a colon counts as no
        credentials at all, which is how a client sending a bearer token reaches a route that
        only looks for Basic.
        """
        authorization = self.header("authorization")
        if authorization is None:
            return None
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != _BASIC:
            return None
        try:
            decoded = b64decode(token, validate=True).decode()
        except ValueError:
            return None
        user, separator, password = decoded.partition(":")
        return (user, password) if separator else None

    def variables(self) -> dict[str, str]:
        """The object the echo routes answer with, in the order described for this module."""
        variables = {
            "SERVER_PROTOCOL": self.protocol,
            "SERVER_NAME": self.server_name,
            "REQUEST_URI": self.target,
            "REQUEST_METHOD": self.method,
        }
        credentials = self.credentials()
        if credentials is not None:
            variables["AUTH_USER"], variables["AUTH_PW"] = credentials
        variables["REMOTE_ADDR"] = self.peer[0]
        variables["REMOTE_PORT"] = self.peer[1]
        for name, _ in self.headers:
            key = "HTTP_" + name.upper().replace("-", "_")
            variables[key] = _joined(self.headers, name) or ""
        return variables


async def read_request(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    server_name: str,
) -> FixtureRequest | None:
    """Read one request, or answer ``None`` for anything that is not one.

    A connection that says nothing, or opens with something that is not a request line, gets
    no answer at all: a client probing the port should see it closed, not a protocol error.
    """
    try:
        head = await reader.readuntil(b"\r\n\r\n")
    except (asyncio.IncompleteReadError, asyncio.LimitOverrunError):
        return None
    lines = head.decode("latin-1").split("\r\n")
    parts = lines[0].split(" ")
    if len(parts) != _REQUEST_LINE_PARTS or not parts[2].startswith("HTTP/"):
        return None
    method, target, protocol = parts
    headers = tuple(
        (name.strip(), value.strip())
        for name, separator, value in (line.partition(":") for line in lines[1:] if line)
        if separator
    )
    return FixtureRequest(
        method=method,
        target=target,
        protocol=protocol,
        headers=headers,
        body=await _read_body(reader, headers),
        peer=_peer(writer),
        server_name=server_name,
    )


def _joined(headers: Sequence[tuple[str, str]], name: str) -> str | None:
    wanted = name.lower()
    values = [value for key, value in headers if key.lower() == wanted]
    return ", ".join(values) if values else None


def _peer(writer: asyncio.StreamWriter) -> tuple[str, str]:
    """The address and port the connection came from, as text, which is how they are echoed."""
    address: tuple[object, ...] = writer.get_extra_info("peername")
    return str(address[0]), str(address[1])


async def _read_body(reader: asyncio.StreamReader, headers: Sequence[tuple[str, str]]) -> bytes:
    transfer_encoding = _joined(headers, "transfer-encoding") or ""
    if "chunked" in transfer_encoding.lower():
        return await _read_chunks(reader)
    declared = _joined(headers, "content-length")
    length = int(declared) if declared is not None and declared.isdigit() else 0
    return await reader.readexactly(length) if length else b""


async def _read_chunks(reader: asyncio.StreamReader) -> bytes:
    body = bytearray()
    while True:
        size = int((await reader.readline()).strip() or b"0", 16)
        if size == 0:
            _ = await reader.readline()
            return bytes(body)
        body += await reader.readexactly(size)
        _ = await reader.readline()

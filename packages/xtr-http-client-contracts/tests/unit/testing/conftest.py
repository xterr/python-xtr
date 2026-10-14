"""A socket and nothing else.

The fixture server exists so an HTTP client can be tested against it, so its own tests may
not lean on an HTTP client: every exchange here is bytes written to a socket and bytes read
back until the peer closes.
"""

from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from xtr_http_client_contracts.testing import TestHttpServer

if TYPE_CHECKING:
    from collections.abc import Iterator

HOST = "127.0.0.1"
READ_SIZE = 65536

# The server the module's `server` fixture is running, which `exchange` talks to when a test
# names no port: the routes and request tests share one server and only care that it answers.
_SERVING: list[TestHttpServer] = []


@dataclass(frozen=True, slots=True)
class RawExchange:
    """One connection's worth of bytes, plus the port it was made from.

    ``local_port`` is what the server should echo back as ``REMOTE_PORT``, which is the only
    variable a test cannot predict without asking the socket.
    """

    raw: bytes
    local_port: int

    @property
    def head(self) -> str:
        return self.raw.split(b"\r\n\r\n", 1)[0].decode("latin-1")

    @property
    def body(self) -> bytes:
        parts = self.raw.split(b"\r\n\r\n", 1)
        return parts[1] if len(parts) == 2 else b""

    @property
    def status_line(self) -> str:
        return self.head.split("\r\n")[0]

    @property
    def status_code(self) -> int:
        return int(self.status_line.split(" ")[1])

    @property
    def headers(self) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        for line in self.head.split("\r\n")[1:]:
            name, _, value = line.partition(":")
            pairs.append((name.strip().lower(), value.strip()))
        return pairs

    def header_values(self, name: str) -> list[str]:
        return [value for key, value in self.headers if key == name.lower()]

    def header(self, name: str) -> str | None:
        values = self.header_values(name)
        return values[0] if values else None

    def json_body(self) -> dict[str, object]:
        return json.loads(self.body)


def exchange(
    payload: bytes,
    *,
    port: int | None = None,
    min_bytes: int | None = None,
    timeout: float = 5.0,
) -> RawExchange:
    """Send ``payload`` on a fresh connection and read until the server closes.

    The connection goes to ``port``, or to the server the module's ``server`` fixture started.
    The sending half is closed straight away, so the server never waits for a request that is
    already complete. ``min_bytes`` hangs up as soon as that many bytes have arrived, which is
    how the routes that write forever are read without waiting for an end that never comes.
    """
    chunks: list[bytes] = []
    received = 0
    target = port if port is not None else serving_port()
    with socket.create_connection((HOST, target), timeout=timeout) as sock:
        local_port: int = sock.getsockname()[1]
        sock.sendall(payload)
        sock.shutdown(socket.SHUT_WR)
        while True:
            data = sock.recv(READ_SIZE)
            if not data:
                break
            chunks.append(data)
            received += len(data)
            if min_bytes is not None and received >= min_bytes:
                break
    return RawExchange(b"".join(chunks), local_port)


def is_listening(port: int, *, timeout: float = 0.5) -> bool:
    """Whether anything answers on ``port``."""
    try:
        with socket.create_connection((HOST, port), timeout=timeout):
            return True
    except OSError:
        return False


def serving_port() -> int:
    """The port of the server the module's ``server`` fixture is running."""
    return _SERVING[-1].port


@pytest.fixture(scope="module")
def server() -> Iterator[TestHttpServer]:
    """One server for the module, as an application's session-scoped fixture would do."""
    with TestHttpServer() as running:
        _SERVING.append(running)
        try:
            yield running
        finally:
            _SERVING.remove(running)

"""A local SMTP server that answers from a script and records what it was told."""

from __future__ import annotations

import asyncio
import re
import socket
import ssl
from typing import TYPE_CHECKING, Self, final

if TYPE_CHECKING:
    from types import TracebackType

__all__ = ["STALL", "ScriptedSmtpServer"]

STALL = "<stall>"
"""A scripted reply that is never sent: the server goes silent at that line instead."""

_END_OF_DATA = b".\r\n"
_END_OF_MESSAGE = b"\r\n.\r\n"
_STUFFED_PERIOD = re.compile(rb"(?m)^\.\.")
_DEFAULT_REPLIES = {
    "HELO": "250 localhost",
    "MAIL": "250 2.0.0 Ok",
    "RCPT": "250 2.0.0 Ok",
    "RSET": "250 2.0.0 Ok",
    "NOOP": "250 2.0.0 Ok",
    "DATA": '354 End data with "." on a line by itself',
    "STARTTLS": "220 2.0.0 Ready to start TLS",
    "AUTH": "235 2.7.0 Authentication successful",
    "QUIT": "221 2.0.0 Bye",
}


@final
class ScriptedSmtpServer:
    """Speaks just enough SMTP for a client to be tested against a real socket.

    Every command is answered with its default reply unless :attr:`replies` holds a
    scripted one for its verb; a scripted reply is used once. While an ``AUTH``
    exchange is under way (the last reply was ``334``), every line is answered
    from the ``AUTH`` script. A scripted :data:`STALL` silences the server at that
    line; a reply's lone surrogates go out as the raw bytes they stand for, so a
    reply can carry bytes that are not UTF-8.

    Attributes:
        greeting: The first reply; ``None`` keeps the server silent.
        capabilities: The extensions ``EHLO`` advertises.
        replies: Scripted replies by verb; ``DATA_END`` answers the end of a message.
        stall: Verbs the server never answers; ``DATA_END`` never answers a message,
            ``DATA_BODY`` stops reading one partway, so the client's writes back up.
        delay: Seconds the server holds its reply to a verb before sending it.
        drop: Verbs at which the server closes the connection without a reply.
        throttle: Reads a message at most ``size`` bytes every ``pause`` seconds,
            like a slow but healthy server, with a small receive buffer so the
            kernel cannot take the message in faster; ``None`` reads it as it comes.
        commands: Every line the server received, without its line ending.
        messages: Every message received after ``DATA``, dot-stuffing removed.
        peers: The address of every client that connected.
        tls_upgrades: How many connections switched to TLS with ``STARTTLS``.
    """

    def __init__(
        self,
        *,
        tls_context: ssl.SSLContext | None = None,
        implicit_tls: bool = False,
    ) -> None:
        """Prepare a server; ``tls_context`` serves ``STARTTLS``, or every connection."""
        self.greeting: str | None = "220 localhost ESMTP ready"
        self.capabilities: list[str] = ["PIPELINING", "8BITMIME"]
        self.replies: dict[str, list[str]] = {}
        self.stall: set[str] = set()
        self.delay: dict[str, float] = {}
        self.drop: set[str] = set()
        self.throttle: tuple[int, float] | None = None
        self.commands: list[str] = []
        self.messages: list[bytes] = []
        self.peers: list[str] = []
        self.tls_upgrades = 0
        self.host = "127.0.0.1"
        self.port = 0
        self._tls_context = tls_context
        self._implicit_tls = implicit_tls
        self._server: asyncio.Server | None = None
        self._writers: list[asyncio.StreamWriter] = []

    async def __aenter__(self) -> Self:
        """Listen on a free local port."""
        self._server = await asyncio.start_server(
            self._serve,
            self.host,
            0,
            ssl=self._tls_context if self._implicit_tls else None,
        )
        self.port = int(self._server.sockets[0].getsockname()[1])  # pyright: ignore[reportAny] — getsockname() is Any in typeshed
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close every connection, then stop listening."""
        for writer in self._writers:
            writer.close()
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._writers.append(writer)
        peer: tuple[str, int] = writer.get_extra_info("peername")  # pyright: ignore[reportAny] — get_extra_info() is Any in typeshed
        self.peers.append(peer[0])
        if self.throttle is not None:
            sock: socket.socket = writer.get_extra_info("socket")  # pyright: ignore[reportAny] — get_extra_info() is Any in typeshed
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.throttle[0])
        try:
            await self._converse(reader, writer)
        except (ConnectionError, OSError):
            pass
        finally:
            writer.close()

    async def _converse(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        if self.greeting is None:
            _ = await reader.read()
            return
        await self._send(writer, self.greeting)
        authenticating = False
        while line := await reader.readline():
            command = line.decode("utf-8", "replace").rstrip("\r\n")
            self.commands.append(command)
            verb = "AUTH" if authenticating else command.partition(" ")[0].upper()
            if verb in self.drop:
                return
            reply = STALL if verb in self.stall else self._scripted(verb) or self._default(verb)
            if reply == STALL:
                _ = await reader.read()
                return
            await asyncio.sleep(self.delay.get(verb, 0))
            await self._send(writer, reply)
            authenticating = verb == "AUTH" and reply.startswith("334")
            match verb:
                case "QUIT":
                    return
                case "DATA" if reply.startswith("354"):
                    if not await self._receive_message(reader, writer):
                        return
                case "STARTTLS" if reply.startswith("220") and self._tls_context is not None:
                    if not await self._start_tls(writer, self._tls_context):
                        return
                case _:
                    pass

    async def _start_tls(self, writer: asyncio.StreamWriter, context: ssl.SSLContext) -> bool:
        transport = writer.transport
        try:
            await writer.start_tls(context)
        except AttributeError:
            # asyncio hands back no transport when the client hangs up as the
            # handshake ends, and the writer then fails on it; put the old one back
            # so the writer can still be closed. The stubs do not declare the
            # attribute, hence vars().
            vars(writer)["_transport"] = transport
            return False
        except (ConnectionError, ssl.SSLError):
            return False
        self.tls_upgrades += 1
        return True

    async def _receive_message(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> bool:
        if "DATA_BODY" in self.stall:
            # Reading nothing lets the socket buffers fill, so the client's writes back up.
            await writer.wait_closed()
            return False
        message = await self._read_message(reader)
        if message is None:
            return False
        self.messages.append(_STUFFED_PERIOD.sub(b".", message))
        if "DATA_END" in self.stall:
            _ = await reader.read()
            return False
        await self._send(writer, self._scripted("DATA_END") or "250 2.0.0 Ok: queued as 1A2B3C")
        return True

    async def _read_message(self, reader: asyncio.StreamReader) -> bytes | None:
        if self.throttle is None:
            lines: list[bytes] = []
            while (line := await reader.readline()) != _END_OF_DATA:
                if not line:
                    return None
                lines.append(line)
            return b"".join(lines)
        size, pause = self.throttle
        received = bytearray()
        while not received.endswith(_END_OF_MESSAGE):
            chunk = await reader.read(size)
            if not chunk:
                return None
            received += chunk
            await asyncio.sleep(pause)
        return bytes(received[: -len(_END_OF_DATA)])

    def _scripted(self, verb: str) -> str | None:
        queue = self.replies.get(verb)
        return queue.pop(0) if queue else None

    def _default(self, verb: str) -> str:
        if verb != "EHLO":
            return _DEFAULT_REPLIES.get(verb, "500 5.5.2 Command not recognized")
        lines = ["localhost", *self.capabilities]
        return "\r\n".join(
            f"250{'-' if index < len(lines) - 1 else ' '}{line}" for index, line in enumerate(lines)
        )

    @staticmethod
    async def _send(writer: asyncio.StreamWriter, reply: str) -> None:
        writer.write(reply.encode("utf-8", "surrogateescape") + b"\r\n")
        await writer.drain()

"""An SMTP server on a thread of its own, answering the moment it has read a command."""

from __future__ import annotations

import os
import socket
import threading
from typing import TYPE_CHECKING, Self, final

if TYPE_CHECKING:
    import io
    import ssl
    from types import TracebackType

__all__ = ["ThreadedSmtpServer"]

_END_OF_DATA = b".\r\n"
_POLL_INTERVAL = 0.05
_IDLE_TIMEOUT = 10.0
_BACKLOG_PAUSE = 0.2


@final
class ThreadedSmtpServer:
    """Speaks SMTP from its own thread, over blocking sockets, outside the client's event loop.

    A server running in the client's loop only gets to answer when the client yields,
    so its replies never reach the client at a moment the client is not waiting for
    one. This server answers as soon as it has read a line, as a remote one does,
    and so catches a client that yields between sending a command and reading its
    reply. It serves one connection at a time.

    Attributes:
        messages: Every message received after ``DATA``, dot-stuffing removed.
        host: The address it listens on.
        port: The port it listens on, once entered.
    """

    def __init__(
        self,
        *,
        tls_context: ssl.SSLContext | None = None,
        forged_record: bytes | None = None,
    ) -> None:
        """Prepare a server.

        Args:
            tls_context: Encrypts every connection from its first byte.
            forged_record: Bytes written straight to the socket, under the TLS layer,
                once a message is under way: after accepting ``DATA`` the server stops
                reading, lets the client's writes back up, then sends these.
        """
        self.messages: list[bytes] = []
        self.host = "127.0.0.1"
        self.port = 0
        self._tls_context = tls_context
        self._forged_record = forged_record
        self._stopped = threading.Event()
        self._listener: socket.socket | None = None
        self._thread: threading.Thread | None = None

    def __enter__(self) -> Self:
        """Listen on a free local port and start serving."""
        listener = socket.create_server((self.host, 0))
        listener.settimeout(_POLL_INTERVAL)
        self.port = int(listener.getsockname()[1])  # pyright: ignore[reportAny] — getsockname() is Any in typeshed
        self._listener = listener
        self._thread = threading.Thread(target=self._run, args=(listener,), daemon=True)
        self._thread.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Stop serving and wait for the thread to end."""
        self._stopped.set()
        if self._thread is not None:
            self._thread.join(_IDLE_TIMEOUT)
        if self._listener is not None:
            self._listener.close()

    def _run(self, listener: socket.socket) -> None:
        while not self._stopped.is_set():
            try:
                connection = listener.accept()[0]
            except TimeoutError:
                continue
            connection.settimeout(_IDLE_TIMEOUT)
            try:
                self._serve(connection)
            except OSError:
                pass
            finally:
                connection.close()

    def _serve(self, connection: socket.socket) -> None:
        sock = (
            self._tls_context.wrap_socket(connection, server_side=True)
            if self._tls_context is not None
            else connection
        )
        with sock, sock.makefile("rb") as stream:
            sock.sendall(b"220 localhost ESMTP ready\r\n")
            while line := stream.readline():
                match line.partition(b" ")[0].strip().upper():
                    case b"EHLO":
                        sock.sendall(b"250-localhost\r\n250 8BITMIME\r\n")
                    case b"DATA":
                        sock.sendall(b'354 End data with "." on a line by itself\r\n')
                        if self._forged_record is not None:
                            self._forge(sock, self._forged_record)
                            return
                        self.messages.append(_read_message(stream))
                        sock.sendall(f"250 2.0.0 Ok: queued as {len(self.messages)}\r\n".encode())
                    case b"QUIT":
                        sock.sendall(b"221 2.0.0 Bye\r\n")
                        return
                    case _:
                        sock.sendall(b"250 2.0.0 Ok\r\n")

    def _forge(self, sock: socket.socket, record: bytes) -> None:
        _ = self._stopped.wait(_BACKLOG_PAUSE)
        _ = os.write(sock.fileno(), record)
        # Keep reading until the client hangs up: closing with its bytes unread would
        # reset the connection, and the reset could overtake the forged record.
        while sock.recv(64 * 1024):
            pass


def _read_message(stream: io.BufferedReader) -> bytes:
    lines: list[bytes] = []
    while (line := stream.readline()) != _END_OF_DATA:
        if not line:
            break
        lines.append(line[1:] if line.startswith(b"..") else line)
    return b"".join(lines)

"""The threaded server speaks SMTP the way the client tests rely on."""

from __future__ import annotations

import socket
import ssl
from typing import TYPE_CHECKING

import pytest

from tests.support.certificates import make_certificate
from tests.support.threaded_smtp_server import ThreadedSmtpServer

if TYPE_CHECKING:
    import io
    from pathlib import Path


def _ask(sock: socket.socket, stream: io.BufferedReader, line: bytes) -> bytes:
    sock.sendall(line)
    return stream.readline()


def test_it_answers_every_command_and_records_each_message() -> None:
    with (
        ThreadedSmtpServer() as server,
        socket.create_connection((server.host, server.port)) as sock,
    ):
        stream = sock.makefile("rb")
        greeting = stream.readline()
        replies = [
            _ask(sock, stream, b"MAIL FROM:<a@example.com>\r\n"),
            _ask(sock, stream, b"DATA\r\n"),
            _ask(sock, stream, b"..one\r\n.\r\n"),
            _ask(sock, stream, b"DATA\r\n"),
            _ask(sock, stream, b"two\r\n.\r\n"),
            _ask(sock, stream, b"QUIT\r\n"),
        ]
        stream.close()

    assert greeting == b"220 localhost ESMTP ready\r\n"
    assert replies == [
        b"250 2.0.0 Ok\r\n",
        b'354 End data with "." on a line by itself\r\n',
        b"250 2.0.0 Ok: queued as 1\r\n",
        b'354 End data with "." on a line by itself\r\n',
        b"250 2.0.0 Ok: queued as 2\r\n",
        b"221 2.0.0 Bye\r\n",
    ]
    assert server.messages == [b".one\r\n", b"two\r\n"]


def test_a_forged_record_reaches_the_client_under_the_tls_layer(tmp_path: Path) -> None:
    client_context = ssl.create_default_context()
    client_context.minimum_version = ssl.TLSVersion.TLSv1_2
    client_context.check_hostname = False
    client_context.verify_mode = ssl.CERT_NONE
    forged = b"\x17\x03\x03\x00\x20" + bytes(32)
    with (
        ThreadedSmtpServer(
            tls_context=make_certificate(tmp_path).server_context(), forged_record=forged
        ) as server,
        socket.create_connection((server.host, server.port)) as raw,
        client_context.wrap_socket(raw) as sock,
    ):
        stream = sock.makefile("rb")
        _ = stream.readline()
        reply = _ask(sock, stream, b"DATA\r\n")

        with pytest.raises(ssl.SSLError):
            _ = sock.recv(1024)
        stream.close()

    assert reply == b'354 End data with "." on a line by itself\r\n'

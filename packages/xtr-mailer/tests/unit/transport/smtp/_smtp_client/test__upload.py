from __future__ import annotations

import asyncio
import socket
import struct
from typing import TYPE_CHECKING

import pytest

from tests.support.scripted_smtp_server import ScriptedSmtpServer
from tests.support.smtp_clients import connected_client, send_data, smtp_client
from tests.support.threaded_smtp_server import ThreadedSmtpServer
from xtr_mailer.exception import TransportError, UnexpectedResponseError
from xtr_mailer.transport.smtp._smtp_client import SmtpClient
from xtr_mailer.transport.smtp._smtp_connection_config import SmtpConnectionConfig as Config

if TYPE_CHECKING:
    from tests.support.certificates import Certificate

pytestmark = pytest.mark.anyio


async def test_a_message_is_handed_over_with_its_leading_periods_stuffed() -> None:
    async with ScriptedSmtpServer() as server:
        client = await connected_client(server)
        _ = await client.ehlo()

        _ = await client.execute("MAIL FROM:<sender@example.com> SMTPUTF8", [250])
        _ = await client.execute("RCPT TO:<rcpt@example.com>", [250])
        reply = await send_data(client, b"Subject: hi\r\n\r\n.leading\nbare")
        client.close()

    assert reply == "250 2.0.0 Ok: queued as 1A2B3C"
    assert server.commands[1:4] == [
        "MAIL FROM:<sender@example.com> SMTPUTF8",
        "RCPT TO:<rcpt@example.com>",
        "DATA",
    ]
    assert server.messages == [b"Subject: hi\r\n\r\n.leading\r\nbare\r\n"]


async def test_every_message_is_accepted_by_a_server_answering_from_another_thread() -> None:
    # The server replies the moment it reads the end of a message, so a client that
    # yields between its last write and arming the reply read loses the reply.
    messages = [f"Subject: {index}\r\n".encode() for index in range(20)]
    with ThreadedSmtpServer() as server:
        client = SmtpClient(Config(server.host, server.port, timeout=0.5))
        _ = await client.connect()

        replies = [await send_data(client, message) for message in messages]
        client.close()

    assert replies == [f"250 2.0.0 Ok: queued as {index}" for index in range(1, 21)]
    assert server.messages == messages


async def test_a_refused_message_names_the_completion_code() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["DATA_END"] = ["552 5.3.4 Message too big"]
        client = await connected_client(server)

        with pytest.raises(UnexpectedResponseError) as caught:
            _ = await send_data(client, b"Subject: hi\r\n\r\nbody\r\n")
        client.close()

    assert caught.value.code == 552
    assert caught.value.debug == "> [message]\n< 552 5.3.4 Message too big\n"


async def test_a_closing_server_ends_the_connection() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["DATA_END"] = ["421 4.3.2 Shutting down"]
        client = await connected_client(server)

        with pytest.raises(UnexpectedResponseError):
            _ = await send_data(client, b"Subject: hi\r\n\r\nbody\r\n")

    assert not client.is_connected


async def test_a_message_that_is_never_accepted_times_out_and_closes() -> None:
    async with ScriptedSmtpServer() as server:
        server.stall.add("DATA_END")
        client = smtp_client(server, timeout=0.1)
        _ = await client.connect()

        with pytest.raises(TransportError) as caught:
            _ = await send_data(client, b"Subject: hi\r\n\r\nbody\r\n")

    assert str(caught.value) == f'Connection to "127.0.0.1:{server.port}" timed out.'
    assert caught.value.debug == "> [message]\n"
    assert not client.is_connected


async def test_a_slow_server_still_reading_a_large_message_does_not_time_out() -> None:
    line = b"x" * 1022 + b"\r\n"
    message = line * 4096
    async with ScriptedSmtpServer() as server:
        # About 3 MB/s: the 4 MiB upload outlasts the timeout, while what the buffers
        # still hold after the last write is read well within it.
        server.throttle = (32 * 1024, 0.01)
        client = smtp_client(server, timeout=1.0)
        _ = await client.connect()
        # A small send buffer too, so the upload's pace is the server's, not the kernel's.
        sock: socket.socket = client._smtp.get_transport_info("socket")  # pyright: ignore[reportAny] — aiosmtplib types transport info as Any
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 32 * 1024)

        started = asyncio.get_running_loop().time()
        reply = await send_data(client, message)
        elapsed = asyncio.get_running_loop().time() - started
        client.close()

    assert reply == "250 2.0.0 Ok: queued as 1A2B3C"
    assert server.messages == [message]
    assert elapsed > 1.0  # the whole upload outlasted the timeout, each write did not


async def test_a_server_that_stops_reading_a_message_times_out_and_closes() -> None:
    async with ScriptedSmtpServer() as server:
        server.stall.add("DATA_BODY")
        client = smtp_client(server, timeout=0.2)
        _ = await client.connect()

        with pytest.raises(TransportError) as caught:
            _ = await send_data(client, b"x" * (16 * 1024 * 1024))

    assert str(caught.value) == f'Connection to "127.0.0.1:{server.port}" timed out.'
    assert caught.value.debug == "> [message]\n"
    assert not client.is_connected


async def test_a_server_that_resets_the_connection_mid_message_raises_a_transport_error() -> None:
    async def reset_at_data(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.write(b"220 localhost ESMTP ready\r\n")
        _ = await reader.readline()
        writer.write(b'354 End data with "." on a line by itself\r\n')
        await writer.drain()
        await asyncio.sleep(0.05)
        sock: socket.socket = writer.get_extra_info("socket")  # pyright: ignore[reportAny] — get_extra_info() is Any in typeshed
        # A zero linger turns the close into a reset, as a crashing server's would be.
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        writer.transport.abort()

    server = await asyncio.start_server(reset_at_data, "127.0.0.1", 0)
    port = int(server.sockets[0].getsockname()[1])  # pyright: ignore[reportAny] — getsockname() is Any in typeshed
    client = SmtpClient(Config("127.0.0.1", port, timeout=2.0))
    _ = await client.connect()

    with pytest.raises(TransportError) as caught:
        _ = await send_data(client, b"x" * (16 * 1024 * 1024))
    server.close()
    await server.wait_closed()

    assert str(caught.value) == f'Connection to "127.0.0.1:{port}" has been closed unexpectedly.'
    assert not client.is_connected


async def test_a_tls_record_that_cannot_be_decrypted_mid_message_raises_a_transport_error(
    certificate: Certificate,
) -> None:
    forged = b"\x17\x03\x03\x00\x20" + bytes(32)
    with ThreadedSmtpServer(
        tls_context=certificate.server_context(), forged_record=forged
    ) as server:
        client = SmtpClient(
            Config("localhost", server.port, tls=True, validate_certs=False, timeout=2.0)
        )
        _ = await client.connect()

        with pytest.raises(TransportError) as caught:
            _ = await send_data(client, b"x" * (16 * 1024 * 1024))

    assert str(caught.value) == (
        f'Connection to "ssl://localhost:{server.port}" has been closed unexpectedly.'
    )
    assert caught.value.debug == "> [message]\n"
    assert not client.is_connected


async def test_a_message_body_sent_without_a_connection_raises_a_transport_error() -> None:
    client = SmtpClient(Config("127.0.0.1", 2525))

    with pytest.raises(TransportError, match="has been closed unexpectedly"):
        _ = await client.message(b"x")

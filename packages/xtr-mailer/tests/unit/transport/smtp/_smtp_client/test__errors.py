from __future__ import annotations

import asyncio
import socket

import pytest

from tests.support.scripted_smtp_server import ScriptedSmtpServer
from tests.support.smtp_clients import connected_client, smtp_client
from xtr_mailer.exception import TransportError, UnexpectedResponseError
from xtr_mailer.transport.smtp._smtp_client import SmtpClient
from xtr_mailer.transport.smtp._smtp_connection_config import SmtpConnectionConfig as Config

pytestmark = pytest.mark.anyio


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])  # pyright: ignore[reportAny] — getsockname() is Any in typeshed


# Replies that cannot be read


async def test_a_malformed_reply_is_an_empty_code() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["NOOP"] = ["garbage"]
        client = await connected_client(server)

        with pytest.raises(UnexpectedResponseError) as caught:
            _ = await client.execute("NOOP", [250])
        client.close()

    assert str(caught.value).startswith('Expected response code "250" but got empty code, with')
    assert caught.value.code == 0


async def test_a_malformed_reply_is_named_by_its_own_text_trimmed() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["NOOP"] = ["  hello there  "]
        client = await connected_client(server)

        with pytest.raises(UnexpectedResponseError) as caught:
            _ = await client.execute("NOOP", [250])
        client.close()

    assert str(caught.value) == (
        'Expected response code "250" but got empty code, with message "hello there".'
    )
    assert caught.value.debug == "> NOOP\n< hello there\n"


async def test_a_reply_too_long_to_read_is_an_empty_code() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["NOOP"] = ["250 " + "x" * 9000]
        client = await connected_client(server)

        with pytest.raises(UnexpectedResponseError) as caught:
            _ = await client.execute("NOOP", [250])
        client.close()

    assert str(caught.value) == (
        'Expected response code "250" but got empty code, with message "Response too long".'
    )
    assert caught.value.code == 0
    assert caught.value.debug == "> NOOP\n< Response too long\n"


async def test_a_malformed_reply_leaves_nothing_of_it_in_the_context() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["NOOP"] = ["QQQ s3cret"]
        client = await connected_client(server)
        client.conceal("s3cret")

        with pytest.raises(UnexpectedResponseError) as caught:
            _ = await client.execute("NOOP", [250])
        client.close()

    assert caught.value.__context__ is None
    assert "s3cret" not in str(caught.value)


async def test_a_malformed_greeting_leaves_nothing_of_it_in_the_context() -> None:
    async with ScriptedSmtpServer() as server:
        server.greeting = "QQQ go away"
        client = smtp_client(server)

        with pytest.raises(UnexpectedResponseError) as caught:
            _ = await client.connect()

    assert caught.value.__context__ is None


async def test_a_lost_connection_leaves_nothing_of_the_library_in_the_context() -> None:
    async with ScriptedSmtpServer() as server:
        server.drop.add("NOOP")
        client = await connected_client(server)

        with pytest.raises(TransportError) as caught:
            _ = await client.execute("NOOP", [250])

    assert caught.value.__context__ is None


# Broken connections


async def test_a_refused_connection_raises_a_transport_error() -> None:
    port = _free_port()
    client = SmtpClient(Config("127.0.0.1", port, timeout=1.0))

    with pytest.raises(TransportError) as caught:
        _ = await client.connect()

    assert str(caught.value).startswith(
        f'Connection could not be established with host "127.0.0.1:{port}": '
    )
    assert caught.value.code == 0
    assert not client.is_connected


async def test_a_server_that_never_greets_times_out() -> None:
    async with ScriptedSmtpServer() as server:
        server.greeting = None
        client = smtp_client(server, timeout=0.1)

        with pytest.raises(TransportError) as caught:
            _ = await client.connect()

    assert str(caught.value) == f'Connection to "127.0.0.1:{server.port}" timed out.'


async def test_a_command_that_is_never_answered_times_out_and_closes() -> None:
    async with ScriptedSmtpServer() as server:
        server.stall.add("NOOP")
        client = smtp_client(server, timeout=0.1)
        _ = await client.connect()

        with pytest.raises(TransportError) as caught:
            _ = await client.execute("NOOP", [250])

    assert str(caught.value) == f'Connection to "127.0.0.1:{server.port}" timed out.'
    assert caught.value.debug == "> NOOP\n"
    assert not client.is_connected


async def test_a_server_that_hangs_up_mid_session_raises_a_transport_error() -> None:
    async with ScriptedSmtpServer() as server:
        server.drop.add("MAIL")
        client = await connected_client(server)

        with pytest.raises(TransportError) as caught:
            _ = await client.execute("MAIL FROM:<sender@example.com>", [250])

    assert str(caught.value) == (
        f'Connection to "127.0.0.1:{server.port}" has been closed unexpectedly.'
    )
    assert not client.is_connected


async def test_a_server_that_hangs_up_before_greeting_raises_a_transport_error() -> None:
    def hang_up(_reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.close()

    server = await asyncio.start_server(hang_up, "127.0.0.1", 0)
    port = int(server.sockets[0].getsockname()[1])  # pyright: ignore[reportAny] — getsockname() is Any in typeshed
    client = SmtpClient(Config("127.0.0.1", port))

    with pytest.raises(TransportError) as caught:
        _ = await client.connect()
    server.close()
    await server.wait_closed()

    assert str(caught.value) == f'Connection to "127.0.0.1:{port}" has been closed unexpectedly.'


async def test_a_command_sent_without_a_connection_raises_a_transport_error() -> None:
    client = SmtpClient(Config("127.0.0.1", 2525))

    with pytest.raises(TransportError, match="has been closed unexpectedly"):
        _ = await client.execute("NOOP", [250])

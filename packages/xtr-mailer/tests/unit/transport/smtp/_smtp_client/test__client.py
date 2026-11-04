from __future__ import annotations

import pytest

from tests.support.scripted_smtp_server import ScriptedSmtpServer
from tests.support.smtp_clients import connected_client, smtp_client
from xtr_mailer.exception import (
    InvalidArgumentError,
    LogicError,
    UnexpectedResponseError,
)
from xtr_mailer.transport.smtp._smtp_client import SmtpClient
from xtr_mailer.transport.smtp._smtp_connection_config import SmtpConnectionConfig as Config

pytestmark = pytest.mark.anyio


# Sessions


async def test_connect_returns_the_greeting() -> None:
    async with ScriptedSmtpServer() as server:
        client = smtp_client(server)

        greeting = await client.connect()

        assert greeting == "220 localhost ESMTP ready"
        assert client.is_connected
        assert not client.uses_tls
        client.close()


async def test_ehlo_names_the_local_hostname_and_returns_the_capabilities() -> None:
    async with ScriptedSmtpServer() as server:
        server.capabilities = ["STARTTLS", "AUTH PLAIN login", "SIZE=1000", "BAD_EXT", "8BITMIME"]
        client = await connected_client(server)

        reply = await client.ehlo()
        capabilities = client.capabilities
        client.close()

    assert server.commands == ["EHLO client.example"]
    assert reply.startswith("250-localhost\r\n250-STARTTLS\r\n")
    assert capabilities == {
        "STARTTLS": [],
        "AUTH": ["PLAIN", "LOGIN"],
        "SIZE": ["1000"],
        "8BITMIME": [],
    }


async def test_connecting_again_starts_a_new_session() -> None:
    async with ScriptedSmtpServer() as server:
        client = await connected_client(server)
        _ = await client.ehlo()

        _ = await client.connect()

        assert client.capabilities == {}
        assert client.is_connected
        client.close()

    assert len(server.peers) == 2


async def test_execute_sends_a_raw_command_and_returns_a_multiline_reply_whole() -> None:
    async with ScriptedSmtpServer() as server:
        client = await connected_client(server)

        reply = await client.execute("EHLO raw.example", [250])
        client.close()

    assert reply == "250-localhost\r\n250-PIPELINING\r\n250 8BITMIME"


async def test_the_transcript_holds_the_exchanges_since_it_was_last_taken() -> None:
    async with ScriptedSmtpServer() as server:
        client = await connected_client(server)
        _ = await client.execute("NOOP", [250])
        _ = client.take_transcript()

        _ = await client.execute("RSET", [250])
        transcript = client.take_transcript()
        client.close()

    assert transcript == "> RSET\n< 250 2.0.0 Ok\n"


async def test_a_reply_queued_behind_another_is_pending() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["NOOP"] = ["250 2.0.0 Ok\r\n421 4.4.1 Closing"]
        client = await connected_client(server)
        pending_before = client.has_pending_data

        _ = await client.execute("NOOP", [250])

        assert client.has_pending_data
        client.close()

    assert not pending_before
    assert not client.has_pending_data


def test_its_description_names_the_server() -> None:
    assert SmtpClient(Config("mail.example.com", 465, tls=True)).description == (
        "ssl://mail.example.com:465"
    )


# Refusals


async def test_a_refused_command_raises_with_the_reply_code() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["MAIL"] = ["550 5.7.1 Sender denied"]
        client = await connected_client(server)

        with pytest.raises(UnexpectedResponseError) as caught:
            _ = await client.execute("MAIL FROM:<sender@example.com>", [250])
        client.close()

    assert str(caught.value) == (
        'Expected response code "250" but got code "550", with message "550 5.7.1 Sender denied".'
    )
    assert caught.value.code == 550
    assert caught.value.debug == "> MAIL FROM:<sender@example.com>\n< 550 5.7.1 Sender denied\n"


async def test_every_accepted_code_is_named_in_a_refusal() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["RCPT"] = ["554 no"]
        client = await connected_client(server)

        with pytest.raises(UnexpectedResponseError, match='code "250/251/252" but got code "554"'):
            _ = await client.execute("RCPT TO:<rcpt@example.com>", [250, 251, 252])
        client.close()


async def test_a_refused_greeting_raises_with_the_reply_code() -> None:
    async with ScriptedSmtpServer() as server:
        server.greeting = "554 5.3.2 Go away"
        client = smtp_client(server)

        with pytest.raises(UnexpectedResponseError) as caught:
            _ = await client.connect()

    assert str(caught.value) == (
        'Expected response code "220" but got code "554", with message "554 5.3.2 Go away".'
    )
    assert caught.value.code == 554
    assert not client.is_connected


async def test_a_refused_ehlo_raises_with_the_reply_code() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["EHLO"] = ["502 5.5.1 EHLO not implemented"]
        client = await connected_client(server)

        with pytest.raises(UnexpectedResponseError) as caught:
            _ = await client.ehlo()
        client.close()

    assert caught.value.code == 502
    assert caught.value.debug == "> EHLO client.example\n< 502 5.5.1 EHLO not implemented\n"


async def test_a_blank_reply_adds_no_empty_debug_line() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["NOOP"] = ["   "]
        client = await connected_client(server)

        with pytest.raises(UnexpectedResponseError) as caught:
            _ = await client.execute("NOOP", [250])
        client.close()

    assert str(caught.value) == 'Expected response code "250" but got empty code.'
    assert caught.value.debug == "> NOOP\n"


async def test_a_reply_that_is_not_utf8_reads_with_replacement_characters() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["NOOP"] = ["550 caf\udce9"]
        client = await connected_client(server)

        with pytest.raises(UnexpectedResponseError) as caught:
            _ = await client.execute("NOOP", [250])
        client.close()

    assert str(caught.value).endswith('with message "550 caf\ufffd".')


async def test_a_reply_holding_control_characters_is_shown_escaped() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["MAIL"] = ["550 \x1b[31mdenied\x1b[2J\x07 until\rnow"]
        client = await connected_client(server)

        with pytest.raises(UnexpectedResponseError) as caught:
            _ = await client.execute("MAIL FROM:<sender@example.com>", [250])
        client.close()

    assert str(caught.value) == (
        'Expected response code "250" but got code "550", with message '
        '"550 \\x1b[31mdenied\\x1b[2J\\x07 until\\rnow".'
    )


# Arguments


async def test_a_command_utf8_cannot_write_is_refused_without_quoting_it() -> None:
    async with ScriptedSmtpServer() as server:
        client = await connected_client(server)

        with pytest.raises(InvalidArgumentError) as caught:
            _ = await client.execute("AUTH PLAIN \udcff", [235])
        client.close()

    assert str(caught.value) == "An SMTP command must only hold characters UTF-8 can write."
    assert server.commands == []


async def test_a_command_utf8_cannot_write_is_left_out_of_the_context() -> None:
    async with ScriptedSmtpServer() as server:
        client = await connected_client(server)

        with pytest.raises(InvalidArgumentError) as caught:
            _ = await client.execute("AUTH PLAIN s3cret\udcff", [235])
        client.close()

    assert caught.value.__context__ is None
    assert "s3cret" not in repr(caught.value.args)


async def test_a_command_with_a_line_break_is_refused() -> None:
    async with ScriptedSmtpServer() as server:
        client = await connected_client(server)

        with pytest.raises(InvalidArgumentError):
            _ = await client.execute("NOOP\r\nRSET", [250])
        client.close()

    assert server.commands == []


async def test_a_command_must_accept_some_code() -> None:
    client = SmtpClient(Config())

    with pytest.raises(LogicError, match=r"^You must set the expected response code\.$"):
        _ = await client.execute("NOOP", [])

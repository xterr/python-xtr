"""How an SMTP transport carries on after a refusal, a failed ping or a cancelled connect."""

from __future__ import annotations

import anyio
import pytest
from xtr_clock import MockClock
from xtr_mime import Email

from tests.support.scripted_smtp_server import ScriptedSmtpServer
from tests.support.smtp_sends import envelope, raw, smtp_transport
from xtr_mailer.exception import InvalidArgumentError, UnexpectedResponseError

pytestmark = pytest.mark.anyio


async def test_plain_smtp_never_sends_a_non_ascii_local_part() -> None:
    message = Email().from_("info@dømi.fo").to("dømi@dømi.fo").text(".")
    async with ScriptedSmtpServer() as server:
        with pytest.raises(InvalidArgumentError, match="SMTPUTF8"):
            _ = await smtp_transport(server).send(message)

    assert not any(command.startswith("MAIL") for command in server.commands)


async def test_an_acceptance_naming_no_id_leaves_the_message_id_alone() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["DATA_END"] = ["250 Message accepted"]

        sent = await smtp_transport(server).send(raw(), envelope())

    assert sent is not None
    assert sent.get_message_id() == ""


async def test_a_reset_that_loses_the_connection_ends_the_session() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["RCPT"] = ["550 5.1.1 No such user"]
        server.drop.add("RSET")
        transport = smtp_transport(server)

        with pytest.raises(UnexpectedResponseError):
            _ = await transport.send(raw("Message 1"), envelope())
        server.drop.clear()
        _ = await transport.send(raw("Message 2"), envelope())

    assert len(server.peers) == 2
    assert server.messages == [b"Message 2\r\n"]


async def test_a_server_hanging_up_between_emails_is_connected_to_again() -> None:
    async with ScriptedSmtpServer() as server:
        transport = smtp_transport(server)
        _ = await transport.send(raw("Message 1"), envelope())
        server.hang_up()
        with anyio.fail_after(2):
            while transport._client.is_connected:  # noqa: ASYNC110 — the client signals no event when the server hangs up
                await anyio.sleep(0.01)

        _ = await transport.send(raw("Message 2"), envelope())

    assert len(server.peers) == 2
    assert server.messages == [b"Message 1\r\n", b"Message 2\r\n"]


async def test_a_ping_due_on_a_connection_the_server_closed_opens_a_new_session() -> None:
    clock = MockClock()
    async with ScriptedSmtpServer() as server:
        transport = smtp_transport(server, clock=clock).set_ping_threshold(1)
        _ = await transport.send(raw("Message 1"), envelope())
        server.hang_up()
        with anyio.fail_after(2):
            while transport._client.is_connected:  # noqa: ASYNC110 — the client signals no event when the server hangs up
                await anyio.sleep(0.01)
        clock.sleep(2)

        _ = await transport.send(raw("Message 2"), envelope())

    assert len(server.peers) == 2
    assert server.messages == [b"Message 1\r\n", b"Message 2\r\n"]


async def test_a_refused_ping_opens_a_new_session() -> None:
    clock = MockClock()
    async with ScriptedSmtpServer() as server:
        server.replies["NOOP"] = ["500 5.5.1 Not now"]
        transport = smtp_transport(server, clock=clock).set_ping_threshold(10)
        _ = await transport.send(raw("Message 1"), envelope())
        clock.sleep(11)

        _ = await transport.send(raw("Message 2"), envelope())

    assert "NOOP" in server.commands
    assert len(server.peers) == 2
    assert len(server.messages) == 2


async def test_a_send_cancelled_while_connecting_leaves_no_session() -> None:
    async with ScriptedSmtpServer() as server:
        server.greeting = None
        transport = smtp_transport(server)

        with anyio.move_on_after(0.2):
            _ = await transport.send(raw(), envelope())
        server.greeting = "220 localhost ESMTP ready"
        _ = await transport.send(raw(), envelope())

    assert len(server.peers) == 2
    assert len(server.messages) == 1


async def test_a_send_cancelled_during_its_ping_ends_the_session() -> None:
    clock = MockClock()
    async with ScriptedSmtpServer() as server:
        transport = smtp_transport(server, clock=clock).set_timeout(3).set_ping_threshold(1)
        _ = await transport.send(raw("Message 1"), envelope())
        clock.sleep(2)
        server.delay["NOOP"] = 0.6

        with anyio.move_on_after(0.2):
            _ = await transport.send(raw("Message 2"), envelope())
        connected_after_cancel = transport._client.is_connected
        server.delay.clear()
        _ = await transport.send(raw("Message 3"), envelope())

    assert not connected_after_cancel
    assert len(server.peers) == 2
    assert server.messages == [b"Message 1\r\n", b"Message 3\r\n"]


async def test_a_send_cancelled_during_its_reset_ends_the_session() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["RCPT"] = ["550 5.1.1 No such user"]
        server.delay["RSET"] = 0.6
        transport = smtp_transport(server)

        with anyio.move_on_after(0.2):
            _ = await transport.send(raw("Message 1"), envelope())
        connected_after_cancel = transport._client.is_connected
        server.delay.clear()
        _ = await transport.send(raw("Message 2"), envelope())

    assert not connected_after_cancel
    assert len(server.peers) == 2
    assert server.messages == [b"Message 2\r\n"]

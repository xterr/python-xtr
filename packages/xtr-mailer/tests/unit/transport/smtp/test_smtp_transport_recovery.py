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

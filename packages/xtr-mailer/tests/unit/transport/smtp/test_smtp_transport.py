from __future__ import annotations

import pytest
from xtr_clock import MockClock
from xtr_mime import DataPart, Email, File
from xtr_mime import InvalidArgumentError as MimeInvalidArgumentError

from tests.support.recorded_events import recording_dispatcher
from tests.support.scripted_smtp_server import ScriptedSmtpServer
from tests.support.smtp_sends import email, envelope, raw, smtp_transport
from xtr_mailer.event import SentMessageEvent
from xtr_mailer.exception import (
    InvalidArgumentError,
    LogicError,
    TransportError,
    UnexpectedResponseError,
)
from xtr_mailer.transport import StoppableTransportInterface
from xtr_mailer.transport.smtp import SmtpTransport

pytestmark = pytest.mark.anyio


def _helos(server: ScriptedSmtpServer) -> int:
    return sum(command.startswith("HELO") for command in server.commands)


def test_its_name_is_its_scheme_host_and_any_port_off_the_default() -> None:
    assert str(SmtpTransport()) == "smtps://localhost"
    assert str(SmtpTransport("127.0.0.1", 2525, tls=False)) == "smtp://127.0.0.1:2525"
    assert str(SmtpTransport("mail.example.org", 25, tls=False)) == "smtp://mail.example.org"
    assert str(SmtpTransport("mail.example.org", 25)) == "smtps://mail.example.org"
    assert str(SmtpTransport("mail.example.org", 465, tls=False)) == "smtp://mail.example.org:465"


def test_it_is_a_stoppable_transport() -> None:
    assert isinstance(SmtpTransport(), StoppableTransportInterface)


async def test_a_message_goes_out_as_mail_rcpt_and_data() -> None:
    async with ScriptedSmtpServer() as server:
        transport = smtp_transport(server)

        _ = await transport.send(raw("Message 1"), envelope())

    assert server.commands == [
        "HELO [127.0.0.1]",
        "MAIL FROM:<sender@example.org>",
        "RCPT TO:<recipient@example.org>",
        "DATA",
    ]
    assert server.messages == [b"Message 1\r\n"]


async def test_the_connection_is_reopened_after_a_timeout_rather_than_reset() -> None:
    async with ScriptedSmtpServer() as server:
        server.stall.add("DATA_END")
        transport = smtp_transport(server).set_timeout(0.2).set_ping_threshold(1_000_000)

        with pytest.raises(TransportError, match="timed out"):
            _ = await transport.send(raw("Message 1"), envelope())
        server.stall.clear()
        _ = await transport.send(raw("Message 2"), envelope())

    assert _helos(server) == 2
    assert "RSET" not in server.commands


async def test_the_connection_is_closed_after_a_service_closing_reply() -> None:
    clock = MockClock()
    async with ScriptedSmtpServer() as server:
        server.replies["MAIL"] = ["250 2.0.0 Ok", "421 4.4.1 Connection timed out."]
        transport = smtp_transport(server, clock=clock).set_ping_threshold(0)
        _ = await transport.send(raw("Message 1"), envelope())
        clock.sleep(1)

        with pytest.raises(UnexpectedResponseError) as caught:
            _ = await transport.send(raw("Message 2"), envelope())
        connected_after_refusal = transport._client.is_connected
        _ = await transport.send(raw("Message 3"), envelope())

    assert caught.value.code == 421
    assert not connected_after_refusal
    assert "RSET" not in server.commands
    assert len(server.peers) == 2


async def test_a_service_closing_greeting_closes_the_connection() -> None:
    async with ScriptedSmtpServer() as server:
        server.greeting = "421 4.3.2 Service not available"
        transport = smtp_transport(server)

        with pytest.raises(UnexpectedResponseError) as caught:
            await transport.start()

    assert caught.value.code == 421
    assert not transport._client.is_connected


async def test_a_ping_answered_with_a_queued_reply_reconnects() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["NOOP"] = ["250 2.0.0 OK\r\n421 4.4.1 Connection timed out."]
        transport = smtp_transport(server).set_ping_threshold(-1)

        _ = await transport.send(raw("Message 1"), envelope())
        _ = await transport.send(raw("Message 2"), envelope())

    assert _helos(server) == 2
    assert len(server.messages) == 2


async def test_a_send_below_the_ping_threshold_does_not_ping() -> None:
    async with ScriptedSmtpServer() as server:
        transport = smtp_transport(server, clock=MockClock())

        for index in range(3):
            _ = await transport.send(raw(f"Message {index}"), envelope())

    assert "NOOP" not in server.commands


async def test_a_send_after_a_transport_error_reconnects() -> None:
    async with ScriptedSmtpServer() as server:
        transport = smtp_transport(server)
        _ = await transport.send(raw("Message 1"), envelope())
        server.drop.add("MAIL")

        with pytest.raises(TransportError):
            _ = await transport.send(raw("Message 2"), envelope())
        connected_after_failure = transport._client.is_connected
        server.drop.clear()
        _ = await transport.send(raw("Message 3"), envelope())

    assert not connected_after_failure
    assert len(server.peers) == 2


async def test_a_send_above_the_ping_threshold_pings_first() -> None:
    clock = MockClock()
    async with ScriptedSmtpServer() as server:
        transport = smtp_transport(server, clock=clock).set_ping_threshold(1)
        _ = await transport.send(raw("Message 1"), envelope())
        _ = await transport.send(raw("Message 2"), envelope())
        before = list(server.commands)
        clock.sleep(1.5)

        _ = await transport.send(raw("Message 3"), envelope())

    assert "NOOP" not in before
    assert server.commands[len(before)] == "NOOP"


async def test_an_email_that_cannot_be_rendered_never_connects() -> None:
    async with ScriptedSmtpServer() as server:
        transport = smtp_transport(server).set_ping_threshold(1)
        message = email().add_part(DataPart(File("/does_not_exists")))

        with pytest.raises(MimeInvalidArgumentError, match=r'(?i)path "/does_not_exists"'):
            _ = await transport.send(message)

    assert server.peers == []


async def test_the_envelope_is_written_with_its_domains_encoded() -> None:
    message = (
        Email()
        .from_("sender@exämple.org")
        .add_to("recipient@exämple.org", "recipient2@example.org")
        .text(".")
    )
    async with ScriptedSmtpServer() as server:
        _ = await smtp_transport(server).send(message)

    assert "MAIL FROM:<sender@xn--exmple-cua.org>" in server.commands
    assert "RCPT TO:<recipient@xn--exmple-cua.org>" in server.commands
    assert "RCPT TO:<recipient2@example.org>" in server.commands


@pytest.mark.parametrize(
    "domain",
    [
        "evil\r\nMAIL FROM:<injected@example.org>",
        "example.org\r",
        "example.org\n",
        "example.org\x00",
        "example.org\t",
        "example.org\x7f",
        "exam\x01ple.org",
    ],
)
def test_a_local_domain_with_control_characters_is_refused(domain: str) -> None:
    with pytest.raises(
        InvalidArgumentError,
        match=r"^The local domain name must not contain control characters\.$",
    ):
        _ = SmtpTransport().set_local_domain(domain)


@pytest.mark.parametrize(
    ("domain", "expected"),
    [
        ("mail.example.org", "mail.example.org"),
        ("192.0.2.1", "[192.0.2.1]"),
        ("2001:db8::1", "[IPv6:2001:db8::1]"),
        ("[192.0.2.1]", "[192.0.2.1]"),
    ],
)
def test_a_local_domain_that_is_an_address_is_bracketed(domain: str, expected: str) -> None:
    assert SmtpTransport().set_local_domain(domain).get_local_domain() == expected


def test_the_local_domain_defaults_to_the_loopback_address() -> None:
    assert SmtpTransport().get_local_domain() == "[127.0.0.1]"


async def test_the_local_domain_is_the_one_helo_names() -> None:
    async with ScriptedSmtpServer() as server:
        transport = smtp_transport(server).set_local_domain("client.example.org")

        await transport.start()
        await transport.stop()

    assert server.commands[0] == "HELO client.example.org"


async def test_the_message_id_the_server_gives_is_the_sent_message_s() -> None:
    dispatcher, recorded = recording_dispatcher()
    async with ScriptedSmtpServer() as server:
        server.replies["DATA_END"] = ["250 OK queued as 000501c4054c"]
        transport = smtp_transport(server, event_dispatcher=dispatcher)

        _ = await transport.send(email())

    sent = [event for event in recorded if isinstance(event, SentMessageEvent)]
    assert [event.get_message().get_message_id() for event in sent] == ["000501c4054c"]


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        ("250 2.0.0 Ok: queued as 1A2B3C", "1A2B3C"),
        ("250 OK id=1lvBzP-0003xa-Ql", "1lvBzP-0003xa-Ql"),
        ("250 Ok 0123456789AB", "0123456789AB"),
        ("250-first\r\n250 2.0.0 Ok: queued as XYZ", "XYZ"),
        ("250 Message accepted", ""),
    ],
)
def test_the_message_id_is_read_from_the_acceptance(reply: str, expected: str) -> None:
    assert SmtpTransport()._parse_message_id(reply) == expected


async def test_a_command_must_accept_some_code() -> None:
    with pytest.raises(LogicError, match=r"^You must set the expected response code\.$"):
        _ = await SmtpTransport().execute_command("NOOP", [])


async def test_an_empty_reply_is_an_empty_code() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["NOOP"] = ["   "]
        transport = smtp_transport(server)
        await transport.start()

        with pytest.raises(UnexpectedResponseError) as caught:
            _ = await transport.execute_command("NOOP", [220])
        await transport.stop()

    assert str(caught.value) == 'Expected response code "220" but got empty code.'


async def test_an_unexpected_code_is_named_with_the_reply() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["NOOP"] = ["550 Access Denied"]
        transport = smtp_transport(server)
        await transport.start()

        with pytest.raises(UnexpectedResponseError) as caught:
            _ = await transport.execute_command("NOOP", [220])
        await transport.stop()

    assert str(caught.value) == (
        'Expected response code "220" but got code "550", with message "550 Access Denied".'
    )
    assert caught.value.code == 550

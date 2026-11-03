"""Emails sent through the mailer end to end: queued, sent now, signed, overridden."""

from __future__ import annotations

import dkim
import pytest
from xtr_event_dispatcher import EventDispatcher
from xtr_messenger import HandleMessageMiddleware, HandlersLocator, MessageBus
from xtr_messenger.stamp import TransportNamesStamp
from xtr_mime import Email, Message
from xtr_mime.crypto import DkimOptions, DkimSigner
from xtr_mime.header import Headers

from tests.support.dkim_keys import SELECTOR, private_key_pem, published_key
from tests.support.recording_bus import RecordingBus
from tests.support.scripted_smtp_server import ScriptedSmtpServer
from xtr_mailer import Mailer
from xtr_mailer.event import MessageEvent
from xtr_mailer.event_listener import (
    DkimSignedMessageListener,
    EnvelopeListener,
    MessageListener,
    MessageLoggerListener,
    MessengerTransportListener,
)
from xtr_mailer.messenger import MessageHandler, SendEmailMessage
from xtr_mailer.transport import NullTransport, Transports
from xtr_mailer.transport.smtp import EsmtpTransport

pytestmark = pytest.mark.anyio


def _email(subject: str) -> Email:
    return Email().from_("sender@example.com").to("recipient@example.com").subject(subject)


def _logged(dispatcher: EventDispatcher) -> MessageLoggerListener:
    logger = MessageLoggerListener()
    dispatcher.add_listener(MessageEvent, logger.on_message, priority=logger.PRIORITY)
    return logger


def _status(event: MessageEvent) -> None:
    message = event.get_message()
    assert isinstance(message, Message)
    _ = message.get_headers().add_text_header("X-Status", "queued" if event.is_queued() else "sent")


def _subjects_and_status(messages: list[object]) -> list[tuple[str | None, object]]:
    shown: list[tuple[str | None, object]] = []
    for message in messages:
        assert isinstance(message, Email)
        shown.append((message.get_subject(), message.get_headers().get_header_body("X-Status")))
    return shown


async def test_a_message_sent_through_a_synchronous_bus_is_reported_once() -> None:
    dispatcher = EventDispatcher()
    logger = _logged(dispatcher)
    dispatcher.add_listener(MessageEvent, _status)
    transports = Transports({"main": NullTransport(dispatcher)})
    handlers = HandlersLocator()
    _ = handlers.register(SendEmailMessage, MessageHandler(transports))
    mailer = Mailer(transports, MessageBus([HandleMessageMiddleware(handlers)]), dispatcher)

    await mailer.send(_email("First").text("Hello"))
    await mailer.send(_email("Second").text("Hello"))

    events = logger.get_events()
    assert len(events.get_events()) == 4
    assert _subjects_and_status(list(events.get_messages())) == [
        ("First", "sent"),
        ("Second", "sent"),
    ]


async def test_a_message_left_in_the_queue_is_still_reported() -> None:
    dispatcher = EventDispatcher()
    logger = _logged(dispatcher)
    dispatcher.add_listener(MessageEvent, _status)
    mailer = Mailer(Transports({"main": NullTransport(dispatcher)}), MessageBus([]), dispatcher)

    await mailer.send(_email("First").text("Hello"))
    await mailer.send(_email("Second").text("Hello"))

    events = logger.get_events()
    assert len(events.get_events()) == 2
    assert _subjects_and_status(list(events.get_messages())) == [
        ("First", "queued"),
        ("Second", "queued"),
    ]


async def test_a_queued_message_is_kept_when_an_email_was_sent_before() -> None:
    dispatcher = EventDispatcher()
    logger = _logged(dispatcher)
    transports = Transports({"main": NullTransport(dispatcher)})

    await Mailer(transports, None, dispatcher).send(_email("Sent").text("Hello"))
    await Mailer(transports, MessageBus([]), dispatcher).send(_email("Queued").text("Hello"))

    messages = logger.get_events().get_messages()
    assert [m.get_subject() for m in messages if isinstance(m, Email)] == ["Sent", "Queued"]


async def test_the_bus_transport_header_routes_the_queued_email() -> None:
    dispatcher, bus = EventDispatcher(), RecordingBus()
    dispatcher.add_listener(MessageEvent, MessengerTransportListener().on_message)
    email = _email("Routed").text("Hello")
    _ = email.get_headers().add_text_header("X-Bus-Transport", "async, priority")

    await Mailer(NullTransport(dispatcher), bus, dispatcher).send(email)

    [(message, stamps)] = bus.dispatched
    assert isinstance(message, SendEmailMessage)
    assert message.message is email
    assert stamps == (TransportNamesStamp(("async", "priority")),)


def _listened(dispatcher: EventDispatcher, canonicalization: str) -> None:
    options = DkimOptions().header_canon(canonicalization).body_canon(canonicalization)
    signer = DkimSigner(private_key_pem(), "example.com", SELECTOR, default_options=options)
    listeners = [
        MessageListener(Headers().add_text_header("X-Campaign", "spring")),
        DkimSignedMessageListener(signer),
        EnvelopeListener("bounces@example.com"),
    ]
    for listener in listeners:
        dispatcher.add_listener(MessageEvent, listener.on_message, priority=listener.PRIORITY)


@pytest.mark.parametrize("canonicalization", ["simple", "relaxed"])
async def test_a_signed_email_verifies_at_the_server_and_reaches_its_hidden_recipient(
    canonicalization: str,
) -> None:
    dispatcher = EventDispatcher()
    _listened(dispatcher, canonicalization)
    email = (
        _email("Über alles")
        .cc("copy@example.com")
        .bcc("hidden@example.com")
        .text("Line one\n.Line starting with a period\nLine three")
        .html("<p>Hello</p>")
    )
    async with ScriptedSmtpServer() as server:
        transport = EsmtpTransport("localhost", server.port, event_dispatcher=dispatcher)
        await Mailer(transport, None, dispatcher).send(email)
        await transport.stop()

    [received] = server.messages
    assert [command for command in server.commands if command.startswith(("MAIL", "RCPT"))] == [
        "MAIL FROM:<bounces@example.com>",
        "RCPT TO:<recipient@example.com>",
        "RCPT TO:<copy@example.com>",
        "RCPT TO:<hidden@example.com>",
    ]
    assert b"hidden@example.com" not in received
    assert b"X-Campaign: spring" in received
    assert dkim.verify(received, dnsfunc=published_key)

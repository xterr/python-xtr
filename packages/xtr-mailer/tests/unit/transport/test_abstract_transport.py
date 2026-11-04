from __future__ import annotations

import pytest
from xtr_event_dispatcher import EventDispatcher
from xtr_mime import Address, Email, MimeError, RawMessage

from tests.support.fake_transport import FakeTransport
from tests.support.recorded_events import recording_dispatcher
from xtr_mailer import Envelope, LogicError, RemoteTemplateEmail, SentMessage
from xtr_mailer.event import FailedMessageEvent, MessageEvent, SentMessageEvent
from xtr_mailer.transport import NullTransport

pytestmark = pytest.mark.anyio


def _envelope() -> Envelope:
    return Envelope(Address("fabien@example.com"), [Address("helene@example.com")])


def _email() -> Email:
    return Email().from_("fabien@example.com").to("helene@example.com").text("Hello!")


async def test_it_sends_without_events_when_it_has_no_dispatcher() -> None:
    transport = FakeTransport()

    sent = await transport.send(_email())

    assert isinstance(sent, SentMessage)
    assert transport.sent == [sent]


async def test_it_announces_the_email_before_and_the_send_after() -> None:
    dispatcher, recorded = recording_dispatcher()

    sent = await FakeTransport(dispatcher).send(_email())

    assert [type(event) for event in recorded] == [MessageEvent, SentMessageEvent]
    before, after = recorded
    assert isinstance(before, MessageEvent)
    assert before.get_transport() == "fake://"
    assert not before.is_queued()
    assert isinstance(after, SentMessageEvent)
    assert after.get_message() is sent


async def test_the_envelope_is_read_from_the_email_when_none_is_given() -> None:
    sent = await FakeTransport().send(_email())

    assert sent is not None
    assert sent.get_envelope().get_sender().get_address() == "fabien@example.com"
    assert [r.get_address() for r in sent.get_envelope().get_recipients()] == ["helene@example.com"]


async def test_a_raw_message_needs_an_envelope() -> None:
    with pytest.raises(LogicError, match="without an explicit Envelope"):
        _ = await NullTransport().send(RawMessage(b"Some raw email message"))


async def test_listeners_change_a_copy_and_the_copy_is_sent() -> None:
    dispatcher = EventDispatcher()
    other = Envelope(Address("bounces@example.com"), [Address("other@example.com")])

    def change(event: MessageEvent) -> None:
        message = event.get_message()
        assert isinstance(message, Email)
        _ = message.get_headers().add_text_header("X-Changed", "yes")
        event.get_envelope().set_sender(Address("changed@example.com"))
        event.set_envelope(other)

    dispatcher.add_listener(MessageEvent, change)
    email = _email()
    envelope = _envelope()

    sent = await FakeTransport(dispatcher).send(email, envelope)

    assert sent is not None
    assert sent.get_envelope() is other
    assert "X-Changed: yes" in sent.to_string()
    assert not email.get_headers().has("X-Changed")
    assert envelope.get_sender().get_address() == "fabien@example.com"


async def test_a_failed_send_is_announced_then_raised() -> None:
    dispatcher, recorded = recording_dispatcher()
    transport = FakeTransport(dispatcher)
    error = RuntimeError("down")
    transport.error = error

    with pytest.raises(RuntimeError) as caught:
        _ = await transport.send(_email())

    assert caught.value is error
    assert [type(event) for event in recorded] == [MessageEvent, FailedMessageEvent]
    failed = recorded[1]
    assert isinstance(failed, FailedMessageEvent)
    assert failed.get_error() is error
    before = recorded[0]
    assert isinstance(before, MessageEvent)
    assert failed.get_message() is before.get_message()


async def test_an_email_that_cannot_be_rendered_is_announced_as_failed() -> None:
    dispatcher, recorded = recording_dispatcher()
    transport = FakeTransport(dispatcher)
    bodiless = Email().from_("fabien@example.com").to("helene@example.com")

    with pytest.raises(MimeError) as caught:
        _ = await transport.send(bodiless)

    assert [type(event) for event in recorded] == [MessageEvent, FailedMessageEvent]
    failed = recorded[1]
    assert isinstance(failed, FailedMessageEvent)
    assert failed.get_error() is caught.value
    assert transport.sent == []


async def test_a_rejected_email_is_not_sent() -> None:
    dispatcher = EventDispatcher()

    def reject(event: MessageEvent) -> None:
        event.reject()

    def never(event: MessageEvent) -> None:
        del event
        pytest.fail("A listener after the rejection was called.")

    dispatcher.add_listener(MessageEvent, reject, 255)
    dispatcher.add_listener(MessageEvent, never)
    transport = FakeTransport(dispatcher)

    assert await transport.send(RawMessage(b""), _envelope()) is None
    assert transport.sent == []


async def test_a_remote_template_is_refused_by_a_transport_that_cannot_send_one() -> None:
    email = (
        RemoteTemplateEmail()
        .from_("fabien@example.com")
        .to("helene@example.com")
        .template("welcome", {"firstName": "Fabien"})
    )

    with pytest.raises(LogicError) as caught:
        _ = await FakeTransport(EventDispatcher()).send(email)

    assert str(caught.value) == (
        'The "tests.support.fake_transport.FakeTransport" transport does not support sending '
        "emails rendered from a remote template."
    )


async def test_a_remote_template_is_refused_without_a_dispatcher_too() -> None:
    email = RemoteTemplateEmail().from_("f@example.com").to("h@example.com").template("welcome")

    with pytest.raises(LogicError, match="remote template"):
        _ = await FakeTransport().send(email)


async def test_a_remote_template_is_sent_by_a_transport_able_to() -> None:
    email = (
        RemoteTemplateEmail()
        .from_("fabien@example.com")
        .to("helene@example.com")
        .template("welcome", {"firstName": "Fabien"})
    )

    assert await NullTransport(EventDispatcher()).send(email) is not None


async def test_a_remote_template_email_without_a_template_is_an_ordinary_email() -> None:
    email = RemoteTemplateEmail().from_("f@example.com").to("h@example.com").text("Hi")

    assert await FakeTransport().send(email) is not None


async def test_a_message_read_once_sends_the_same_bytes_each_time_it_is_sent() -> None:
    transport = FakeTransport()
    message = RawMessage(iter([b"Subject: Hi\r\n", b"\r\n", b"Hello!\r\n"]))

    _ = await transport.send(message, _envelope())
    _ = await transport.send(message, _envelope())

    assert [b"".join(sent.to_iterable()) for sent in transport.sent] == [
        b"Subject: Hi\r\n\r\nHello!\r\n"
    ] * 2

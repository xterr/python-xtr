"""The mailer: an email sent through the transport now, or queued on a message bus."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from typing_extensions import override
from xtr_event_dispatcher import EventDispatcher
from xtr_messenger import Envelope as BusEnvelope
from xtr_messenger import HandlersFailedError, NoHandlerForMessageError
from xtr_messenger.stamp import StampInterface
from xtr_mime import Address, Email, RawMessage

from tests.support.dummy_transport import DummyTransport
from tests.support.fake_transport import FakeTransport
from tests.support.recording_bus import RecordingBus
from xtr_mailer import Envelope, LogicError, Mailer, MailerInterface, TransportError
from xtr_mailer.event import MessageEvent
from xtr_mailer.messenger import SendEmailMessage

pytestmark = pytest.mark.anyio


@dataclass(frozen=True, slots=True)
class _Stamp(StampInterface):
    pass


def _email(subject: str = "Time for the mailer!") -> Email:
    return (
        Email()
        .from_("hello@example.com")
        .to("you@example.com")
        .subject(subject)
        .text("Sending emails is fun again!")
        .html("<p>See the HTML part.</p>")
    )


def _queued_events(dispatcher: EventDispatcher) -> list[MessageEvent]:
    events: list[MessageEvent] = []
    dispatcher.add_listener(MessageEvent, events.append)
    return events


def _reject(event: MessageEvent) -> None:
    event.reject()


def test_it_is_a_mailer() -> None:
    assert isinstance(Mailer(DummyTransport("localhost")), MailerInterface)


async def test_a_raw_message_cannot_be_queued_without_an_envelope() -> None:
    mailer = Mailer(DummyTransport("localhost"), RecordingBus(), EventDispatcher())

    with pytest.raises(LogicError) as caught:
        await mailer.send(RawMessage("Some raw email message"))

    assert str(caught.value) == "Cannot send a RawMessage instance without an explicit Envelope."


async def test_a_queued_email_is_dispatched_on_the_bus_with_the_stamps_listeners_added() -> None:
    bus, dispatcher, stamp = RecordingBus(), EventDispatcher(), _Stamp()
    subjects: list[str | None] = []

    def stamp_it(event: MessageEvent) -> None:
        event.add_stamp(stamp)
        message = event.get_message()
        assert isinstance(message, Email)
        subjects.append(message.get_subject())

    dispatcher.add_listener(MessageEvent, stamp_it)
    mailer = Mailer(FakeTransport(dispatcher), bus, dispatcher)
    email = _email()

    await mailer.send(email)

    assert subjects == ["Time for the mailer!"]
    [(message, stamps)] = bus.dispatched
    assert isinstance(message, SendEmailMessage)
    assert message.message is email
    assert message.envelope is None
    assert stamps == (stamp,)


async def test_a_rejected_email_is_never_sent() -> None:
    dispatcher = EventDispatcher()
    dispatcher.add_listener(MessageEvent, _reject, priority=255)

    def never(event: MessageEvent) -> None:
        del event
        msg = "Should never be called."
        raise AssertionError(msg)

    dispatcher.add_listener(MessageEvent, never)
    transport = FakeTransport(dispatcher)
    envelope = Envelope(Address("fabien@example.com"), [Address("helene@example.com")])

    await Mailer(transport).send(RawMessage(""), envelope)

    assert transport.sent == []


async def test_without_a_bus_the_email_is_sent_through_the_transport() -> None:
    transport = FakeTransport()
    email = _email()

    await Mailer(transport, None, EventDispatcher()).send(email)

    [sent] = transport.sent
    assert sent.get_original_message() is not email
    assert sent.get_envelope().get_recipients() == [Address("you@example.com")]


async def test_without_a_bus_the_explicit_envelope_is_the_one_sent_with() -> None:
    transport = FakeTransport()
    envelope = Envelope(Address("bounces@example.com"), [Address("other@example.com")])

    await Mailer(transport).send(_email(), envelope)

    [sent] = transport.sent
    assert sent.get_envelope().get_sender() == Address("bounces@example.com")
    assert sent.get_envelope().get_recipients() == [Address("other@example.com")]


async def test_the_queued_event_names_the_transport_and_says_it_is_queued() -> None:
    dispatcher = EventDispatcher()
    events = _queued_events(dispatcher)

    await Mailer(FakeTransport(), RecordingBus(), dispatcher).send(_email())

    [event] = events
    assert event.is_queued()
    assert event.get_transport() == "fake://"
    assert event.get_envelope().get_recipients() == [Address("you@example.com")]


async def test_listeners_change_a_copy_and_the_original_email_is_queued() -> None:
    bus, dispatcher = RecordingBus(), EventDispatcher()

    def change(event: MessageEvent) -> None:
        message = event.get_message()
        assert isinstance(message, Email)
        _ = message.subject("Changed").add_bcc("hidden@example.com")
        event.get_envelope().set_sender(Address("changed@example.com"))

    dispatcher.add_listener(MessageEvent, change)
    email = _email()
    envelope = Envelope(Address("bounces@example.com"), [Address("you@example.com")])

    await Mailer(FakeTransport(), bus, dispatcher).send(email, envelope)

    [(message, _)] = bus.dispatched
    assert isinstance(message, SendEmailMessage)
    assert message.message is email
    assert message.envelope is envelope
    assert email.get_subject() == "Time for the mailer!"
    assert email.get_bcc() == []
    assert envelope.get_sender() == Address("bounces@example.com")


async def test_a_rejected_queued_email_is_not_dispatched() -> None:
    bus, dispatcher = RecordingBus(), EventDispatcher()
    dispatcher.add_listener(MessageEvent, _reject)

    await Mailer(FakeTransport(), bus, dispatcher).send(_email())

    assert bus.dispatched == []


async def test_without_a_dispatcher_the_email_is_queued_without_stamps() -> None:
    bus = RecordingBus()
    email = _email()

    await Mailer(FakeTransport(), bus).send(email)

    [(message, stamps)] = bus.dispatched
    assert isinstance(message, SendEmailMessage)
    assert message.message is email
    assert stamps == ()


async def test_without_a_dispatcher_a_raw_message_is_queued_without_an_envelope() -> None:
    bus, raw = RecordingBus(), RawMessage("Some raw email message")

    await Mailer(FakeTransport(), bus).send(raw)

    [(message, _)] = bus.dispatched
    assert message == SendEmailMessage(raw)


def _handlers_failed(*errors: Exception) -> HandlersFailedError:
    """Build the error the way the bus's handling middleware raises it: from the first error."""
    envelope = BusEnvelope.wrap(SendEmailMessage(_email()))
    failure = HandlersFailedError(envelope, {f"handler{n}": e for n, e in enumerate(errors)})
    failure.__cause__ = errors[0]
    return failure


async def test_the_transport_error_a_handler_raised_is_raised_as_it_is() -> None:
    bus, refused = RecordingBus(), TransportError("Connection refused.")
    bus.error = _handlers_failed(RuntimeError("audit down"), refused, TransportError("second"))

    with pytest.raises(TransportError) as caught:
        await Mailer(FakeTransport(), bus).send(_email())

    assert caught.value is refused


async def test_the_transport_error_a_handler_raised_keeps_its_own_cause() -> None:
    bus, refused = RecordingBus(), TransportError("Connection refused.")
    bus.error = _handlers_failed(refused)

    with pytest.raises(TransportError) as caught:
        await Mailer(FakeTransport(), bus).send(_email())

    assert caught.value.__cause__ is None


async def test_a_handler_failure_without_a_transport_error_is_raised_as_it_is() -> None:
    bus, failure = RecordingBus(), _handlers_failed(RuntimeError("audit down"))
    bus.error = failure

    with pytest.raises(HandlersFailedError) as caught:
        await Mailer(FakeTransport(), bus).send(_email())

    assert caught.value is failure


async def test_any_other_bus_error_goes_through() -> None:
    bus = RecordingBus()
    bus.error = NoHandlerForMessageError(SendEmailMessage, ())

    with pytest.raises(NoHandlerForMessageError):
        await Mailer(FakeTransport(), bus).send(_email())


class _Refusing(FakeTransport):
    @override
    def __str__(self) -> str:
        return "refusing://"


async def test_without_a_bus_the_transport_error_goes_through() -> None:
    transport = _Refusing()
    transport.error = TransportError("Connection refused.")

    with pytest.raises(TransportError, match="Connection refused"):
        await Mailer(transport).send(_email())

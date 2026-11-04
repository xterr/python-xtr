from __future__ import annotations

import pytest
from xtr_mime import Address, Headers, Message, RawMessage, TextPart

from tests.support.fake_transport import FakeTransport
from xtr_mailer import Envelope, InvalidArgumentError, LogicError
from xtr_mailer.transport import TransportInterface, Transports

pytestmark = pytest.mark.anyio


def _message(transport: str | None = None) -> Message:
    headers = Headers()
    if transport is not None:
        _ = headers.add_text_header("X-Transport", transport)
    _ = headers.add_mailbox_list_header("From", ["from@example.com"])
    _ = headers.add_mailbox_list_header("To", ["to@example.com"])
    return Message(headers, TextPart("..."))


def _pair() -> tuple[FakeTransport, FakeTransport, Transports]:
    foo, bar = FakeTransport(), FakeTransport()
    return foo, bar, Transports({"foo": foo, "bar": bar})


def test_it_is_a_transport() -> None:
    assert isinstance(Transports({"foo": FakeTransport()}), TransportInterface)


def test_it_needs_a_transport() -> None:
    with pytest.raises(LogicError) as caught:
        _ = Transports({})

    assert str(caught.value) == (
        '"xtr_mailer.transport.Transports" must have at least one transport configured.'
    )


def test_it_is_named_after_its_transports() -> None:
    assert str(_pair()[2]) == "[foo,bar]"


async def test_an_email_naming_no_transport_goes_to_the_first() -> None:
    foo, bar, transports = _pair()

    _ = await transports.send(_message())

    assert len(foo.sent) == 1
    assert bar.sent == []


async def test_a_raw_message_goes_to_the_first() -> None:
    foo, _, transports = _pair()
    envelope = Envelope(Address("from@example.com"), [Address("to@example.com")])

    sent = await transports.send(RawMessage(b"X-Transport: bar\r\n\r\nHi"), envelope)

    assert foo.sent == [sent]


async def test_the_x_transport_header_picks_the_transport_and_is_removed() -> None:
    foo, bar, transports = _pair()
    message = _message("bar")

    sent = await transports.send(message)

    assert foo.sent == []
    assert bar.sent == [sent]
    assert not message.get_headers().has("X-Transport")
    assert sent is not None
    assert "X-Transport" not in sent.to_string()


async def test_an_unknown_transport_is_refused() -> None:
    _, _, transports = _pair()
    message = _message("foobar")

    with pytest.raises(InvalidArgumentError) as caught:
        _ = await transports.send(message)

    assert str(caught.value) == (
        'The "foobar" transport does not exist (available transports: "foo", "bar").'
    )
    assert message.get_headers().get_header_body("X-Transport") == "foobar"


async def test_a_hostile_transport_name_is_shown_escaped_and_cut_short() -> None:
    _, _, transports = _pair()
    hostile = "a\r\nBcc: x@example.com\x00" + "z" * 100_000

    with pytest.raises(InvalidArgumentError) as caught:
        _ = await transports.send(_message(hostile))

    shown = str(caught.value)
    assert "\r" not in shown
    assert "\n" not in shown
    assert "\x00" not in shown
    assert len(shown) < 200
    assert shown.startswith('The "a\\r\\nBcc: x@example.com\\x00zz')


async def test_the_header_is_restored_when_the_transport_fails() -> None:
    foo = FakeTransport()
    error = RuntimeError("down")
    foo.error = error
    transports = Transports({"foo": foo})
    message = _message("foo")

    with pytest.raises(RuntimeError) as caught:
        _ = await transports.send(message)

    assert caught.value is error
    assert message.get_headers().get_header_body("X-Transport") == "foo"

from __future__ import annotations

import pytest

from tests.support.fake_transport import FakeTransport
from xtr_notifier.exception import InvalidArgumentError, LogicError
from xtr_notifier.message import ChatMessage
from xtr_notifier.transport import TransportInterface, Transports

pytestmark = pytest.mark.anyio


def test_it_is_a_transport_named_after_its_members() -> None:
    transports = Transports({"one": FakeTransport(), "two": FakeTransport()})

    assert isinstance(transports, TransportInterface)
    assert str(transports) == "[one,two]"


def test_it_supports_a_message_one_member_supports() -> None:
    message = ChatMessage("subject")

    assert Transports({"a": FakeTransport(supports=False), "b": FakeTransport()}).supports(message)
    assert not Transports({"a": FakeTransport(supports=False)}).supports(message)


async def test_it_sends_to_the_transport_the_message_names() -> None:
    one = FakeTransport("one")
    message = ChatMessage("subject", transport="one")

    sent = await Transports({"one": one}).send(message)

    assert sent.original_message is message
    assert sent.transport == "one"


async def test_it_sends_to_the_first_supporting_transport_when_the_message_names_none() -> None:
    one = FakeTransport("one", supports=False)
    two = FakeTransport("two")
    message = ChatMessage("subject")

    sent = await Transports({"one": one, "two": two}).send(message)

    assert one.sent == []
    assert sent.original_message is message
    assert sent.transport == "two"


async def test_it_refuses_a_message_no_transport_supports() -> None:
    transports = Transports({"one": FakeTransport(supports=False)})

    with pytest.raises(LogicError) as caught:
        _ = await transports.send(ChatMessage("subject"))

    assert str(caught.value) == (
        'None of the available transports support the given message (available transports: "one").'
    )


async def test_it_refuses_a_message_its_named_transport_does_not_support() -> None:
    one = FakeTransport("one", supports=False)
    two = FakeTransport("two")
    transports = Transports({"one": one, "two": two})
    message = ChatMessage("subject", transport="one")

    with pytest.raises(LogicError) as caught:
        _ = await transports.send(message)

    assert str(caught.value) == 'The "one" transport does not support the given message.'
    assert one.supports_asked == [message]
    assert two.supports_asked == []


async def test_it_refuses_a_message_naming_a_transport_it_does_not_have() -> None:
    one = FakeTransport("one")
    transports = Transports({"one": one})

    with pytest.raises(InvalidArgumentError) as caught:
        _ = await transports.send(ChatMessage("subject", transport="two"))

    assert str(caught.value) == (
        'The "two" transport does not exist (available transports: "one").'
    )
    assert one.supports_asked == []

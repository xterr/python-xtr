from __future__ import annotations

import pytest

from tests.support.dummy_message import DummyMessage
from tests.support.fake_transport import FakeTransport
from xtr_notifier.transport import TransportInterface

pytestmark = pytest.mark.anyio


def test_it_is_a_transport_named_after_its_name() -> None:
    transport = FakeTransport("t1")

    assert isinstance(transport, TransportInterface)
    assert str(transport) == "t1://local"


async def test_it_records_each_send_and_reports_itself_as_the_sender() -> None:
    transport = FakeTransport("t1")
    message = DummyMessage()

    sent = await transport.send(message)

    assert transport.sent == [message]
    assert sent.original_message is message
    assert sent.transport == "t1"


async def test_it_raises_the_scripted_outcomes_in_order_then_succeeds() -> None:
    error = RuntimeError("down")
    transport = FakeTransport(outcomes=[error, None])

    with pytest.raises(RuntimeError):
        _ = await transport.send(DummyMessage())
    _ = await transport.send(DummyMessage())
    _ = await transport.send(DummyMessage())

    assert len(transport.sent) == 3


def test_it_supports_what_it_is_told_to_and_records_each_question() -> None:
    message = DummyMessage()

    assert FakeTransport(supports=False).supports(message) is False
    assert FakeTransport(supports=lambda m: m.subject == "subject").supports(message) is True
    transport = FakeTransport()
    _ = transport.supports(message)
    assert transport.supports_asked == [message]

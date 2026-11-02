from __future__ import annotations

import anyio
import pytest
from xtr_mime import Address, RawMessage

from tests.support.scripted_transport import ScriptedTransport
from xtr_mailer import Envelope, TransportError

pytestmark = pytest.mark.anyio

_ENVELOPE = Envelope(Address("from@example.com"), [Address("to@example.com")])


async def test_it_answers_each_send_with_the_next_outcome_then_sends() -> None:
    error = TransportError("down")
    transport = ScriptedTransport("t1", [error, None])
    message = RawMessage(b"Hi")

    with pytest.raises(TransportError) as caught:
        _ = await transport.send(message, _ENVELOPE)
    second = await transport.send(message, _ENVELOPE)
    third = await transport.send(message, _ENVELOPE)

    assert caught.value is error
    assert transport.sent == [second, third]
    assert transport.received == [message, message, message]


async def test_it_awaits_its_pause_before_answering() -> None:
    gate = anyio.Event()
    transport = ScriptedTransport("t1", pause=gate.wait)

    with anyio.move_on_after(0.01):
        _ = await transport.send(RawMessage(b"Hi"), _ENVELOPE)

    assert len(transport.received) == 1
    assert transport.sent == []


def test_it_is_named_by_its_name() -> None:
    assert str(ScriptedTransport("t1://local")) == "t1://local"

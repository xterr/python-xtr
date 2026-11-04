from __future__ import annotations

import pytest
from xtr_mime import Address, RawMessage

from tests.support.fake_transport import FakeTransport
from xtr_mailer import Envelope

pytestmark = pytest.mark.anyio

_ENVELOPE = Envelope(Address("from@example.com"), [Address("to@example.com")])


async def test_it_keeps_what_it_sends() -> None:
    transport = FakeTransport()

    sent = await transport.send(RawMessage(b"Hi"), _ENVELOPE)

    assert transport.sent == [sent]


async def test_it_raises_the_error_it_is_given_and_keeps_nothing() -> None:
    transport = FakeTransport()
    transport.error = RuntimeError("down")

    with pytest.raises(RuntimeError, match="down"):
        _ = await transport.send(RawMessage(b"Hi"), _ENVELOPE)

    assert transport.sent == []


def test_it_is_named_fake() -> None:
    assert str(FakeTransport()) == "fake://"

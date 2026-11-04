from __future__ import annotations

import anyio
import pytest
from xtr_mime import Address, RawMessage

from tests.support.stalling_transport import StallingTransport
from xtr_mailer import Envelope

pytestmark = pytest.mark.anyio

_ENVELOPE = Envelope(Address("from@example.com"), [Address("to@example.com")])


async def test_its_first_send_hangs_until_cancelled() -> None:
    transport = StallingTransport()

    with anyio.move_on_after(0.01) as scope:
        _ = await transport.send(RawMessage(b"Hi"), _ENVELOPE)

    assert scope.cancelled_caught
    assert transport.sent == []


async def test_a_later_send_goes_through() -> None:
    transport = StallingTransport()
    with anyio.move_on_after(0.01):
        _ = await transport.send(RawMessage(b"Hi"), _ENVELOPE)

    sent = await transport.send(RawMessage(b"Hi"), _ENVELOPE)

    assert transport.sent == [sent]

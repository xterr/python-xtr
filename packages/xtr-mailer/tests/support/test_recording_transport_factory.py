from __future__ import annotations

import pytest
from xtr_mime import Address, RawMessage

from tests.support.recording_transport_factory import DOWN, RecordingTransportFactory
from xtr_mailer import Envelope
from xtr_mailer.exception import TransportError
from xtr_mailer.transport import Dsn

pytestmark = pytest.mark.anyio

_ENVELOPE = Envelope(Address("from@example.com"), [Address("to@example.com")])


async def test_each_transport_keeps_what_it_sends_under_its_name() -> None:
    factory = RecordingTransportFactory()
    transport = factory.create(Dsn.from_string("fake://ops"))

    sent = await transport.send(RawMessage(b"Hi"), _ENVELOPE)

    assert factory.sent == [("ops", sent)]
    assert str(transport) == "fake://ops"


async def test_the_down_transport_fails_and_keeps_nothing() -> None:
    factory = RecordingTransportFactory()
    transport = factory.create(Dsn.from_string(f"fake://{DOWN}"))

    with pytest.raises(TransportError):
        _ = await transport.send(RawMessage(b"Hi"), _ENVELOPE)

    assert factory.sent == []


def test_it_serves_the_fake_scheme_alone() -> None:
    factory = RecordingTransportFactory()

    assert factory.supports(Dsn.from_string("fake://a"))
    assert not factory.supports(Dsn.from_string("null://null"))

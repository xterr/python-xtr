from __future__ import annotations

import pytest
from xtr_event_dispatcher import EventDispatcher
from xtr_http_client import MockHttpClient

from tests.support.dummy_message import DummyMessage
from tests.support.recorded_events import recording_dispatcher
from xtr_notifier.exception import UnsupportedSchemeError
from xtr_notifier.transport import (
    Dsn,
    NullTransport,
    NullTransportFactory,
    TransportFactoryInterface,
)


def test_it_creates_a_null_transport() -> None:
    factory = NullTransportFactory(MockHttpClient(), EventDispatcher())

    assert isinstance(factory, TransportFactoryInterface)
    assert isinstance(factory.create(Dsn("null://null")), NullTransport)


def test_it_supports_the_null_scheme_only() -> None:
    factory = NullTransportFactory()

    assert factory.supports(Dsn("null://null"))
    assert not factory.supports(Dsn("foo://localhost"))


def test_it_refuses_another_scheme() -> None:
    with pytest.raises(UnsupportedSchemeError) as caught:
        _ = NullTransportFactory().create(Dsn("foo://localhost"))

    assert str(caught.value) == (
        'The "foo" scheme is not supported; supported schemes for notifier "null" are: "null".'
    )


@pytest.mark.anyio
async def test_the_transport_announces_on_the_factory_dispatcher() -> None:
    dispatcher, recorded = recording_dispatcher()

    _ = (
        await NullTransportFactory(event_dispatcher=dispatcher)
        .create(Dsn("null://null"))
        .send(DummyMessage())
    )

    assert len(recorded) == 2

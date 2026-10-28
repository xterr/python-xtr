from __future__ import annotations

import pytest
from xtr_http_client import MockHttpClient

from tests.support.dummy_transport_factory import DummyTransportFactory
from tests.support.fake_transport import FakeTransport
from xtr_notifier.exception import UnsupportedSchemeError
from xtr_notifier.transport import Dsn, TransportFactoryInterface


def test_it_is_a_transport_factory_serving_dummy() -> None:
    factory = DummyTransportFactory(MockHttpClient())

    assert isinstance(factory, TransportFactoryInterface)
    assert factory.supports(Dsn("dummy://host"))
    assert not factory.supports(Dsn("other://host"))


def test_it_builds_a_fake_transport_named_after_the_host() -> None:
    transport = DummyTransportFactory(MockHttpClient()).create(Dsn("dummy://t1"))

    assert isinstance(transport, FakeTransport)
    assert transport.name == "t1"


def test_it_refuses_another_scheme() -> None:
    with pytest.raises(UnsupportedSchemeError):
        _ = DummyTransportFactory(MockHttpClient()).create(Dsn("other://host"))

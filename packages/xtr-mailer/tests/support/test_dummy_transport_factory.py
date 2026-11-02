from __future__ import annotations

from xtr_http_client import MockHttpClient

from tests.support.dummy_transport import DummyTransport
from tests.support.dummy_transport_factory import DummyTransportFactory
from xtr_mailer.transport import Dsn


def test_it_serves_the_dummy_scheme_only() -> None:
    factory = DummyTransportFactory(http_client=MockHttpClient())

    assert factory.supports(Dsn("dummy", "a"))
    assert not factory.supports(Dsn("null", "a"))


def test_it_builds_a_transport_for_the_host() -> None:
    transport = DummyTransportFactory(http_client=MockHttpClient()).create(Dsn("dummy", "a"))

    assert isinstance(transport, DummyTransport)
    assert transport.host == "a"

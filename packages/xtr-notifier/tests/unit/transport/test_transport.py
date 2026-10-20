from __future__ import annotations

from importlib.metadata import EntryPoint

import pytest
from xtr_http_client import MockHttpClient

from tests.support.dummy_transport_factory import DummyTransportFactory
from tests.support.fake_transport import FakeTransport
from xtr_notifier import Transport
from xtr_notifier.exception import InvalidArgumentError, UnsupportedSchemeError
from xtr_notifier.transport import (
    Dsn,
    FailoverTransport,
    NullTransport,
    RoundRobinTransport,
    TransportFactoryDiscovery,
    Transports,
)
from xtr_notifier.transport import transport_factory_discovery as discovery_module


def _builder() -> Transport:
    return Transport([DummyTransportFactory(MockHttpClient())])


def test_it_builds_one_transport_from_one_dsn() -> None:
    transport = _builder().from_string("dummy://t1")

    assert isinstance(transport, FakeTransport)
    assert str(transport) == "t1://local"


def test_it_builds_a_failover_from_dsns_joined_by_or() -> None:
    transport = _builder().from_string("dummy://t1 || dummy://t2")

    assert isinstance(transport, FailoverTransport)
    assert str(transport) == "t1://local || t2://local"


def test_it_builds_a_round_robin_from_dsns_joined_by_and() -> None:
    transport = _builder().from_string("dummy://t1 && dummy://t2 && dummy://t3")

    assert type(transport) is RoundRobinTransport
    assert str(transport) == "t1://local && t2://local && t3://local"


def test_failover_is_read_before_round_robin() -> None:
    transport = _builder().from_string("dummy://t1 && dummy://t2 || dummy://t3")

    assert isinstance(transport, FailoverTransport)


def test_it_builds_named_transports_from_named_dsns() -> None:
    transports = _builder().from_strings({"one": "dummy://t1", "two": "dummy://t2"})

    assert isinstance(transports, Transports)
    assert str(transports) == "[one,two]"


class _NullServingFactory:
    def create(self, dsn: Dsn) -> FakeTransport:
        return FakeTransport(dsn.host)

    def supports(self, dsn: Dsn) -> bool:
        return dsn.scheme == "null"


def _advertised_null(*, group: str, name: str | None = None) -> list[EntryPoint]:
    entry = EntryPoint("null", "xtr_notifier.transport:NullTransportFactory", group)
    return [entry] if name in {None, entry.name} else []


def test_a_factory_given_wins_over_a_discovered_one() -> None:
    discovery = TransportFactoryDiscovery(TransportFactoryDiscovery.CHATTER_GROUP)

    transport = Transport([_NullServingFactory()], discovery).from_string("null://given")

    assert isinstance(transport, FakeTransport)


def test_it_finds_an_advertised_factory_when_none_given_serves_the_scheme() -> None:
    builder = Transport(discovery=TransportFactoryDiscovery(TransportFactoryDiscovery.TEXTER_GROUP))

    assert isinstance(builder.from_string("null://null"), NullTransport)


def test_it_refuses_a_scheme_nothing_serves_listing_the_advertised_ones(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    group = TransportFactoryDiscovery.CHATTER_GROUP
    monkeypatch.setattr(discovery_module, "entry_points", _advertised_null)

    with pytest.raises(UnsupportedSchemeError) as caught:
        _ = Transport(discovery=TransportFactoryDiscovery(group)).from_string("other://default")

    assert str(caught.value) == (
        'The "other" scheme is not supported; supported schemes for notifier "chatter" are: "null".'
    )


def test_it_refuses_a_scheme_nothing_serves_without_discovery() -> None:
    with pytest.raises(UnsupportedSchemeError) as caught:
        _ = _builder().from_string("other://default")

    assert str(caught.value) == 'The "other" scheme is not supported.'


def test_it_refuses_an_unreadable_dsn() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = _builder().from_string("dummy://t1 || not-a-dsn")

from __future__ import annotations

from importlib.metadata import EntryPoint

import pytest
from xtr_event_dispatcher import EventDispatcher
from xtr_http_client import MockHttpClient

from tests.support.dummy_transport_factory import DummyTransportFactory
from xtr_notifier.exception import LogicError
from xtr_notifier.transport import Dsn, NullTransportFactory, TransportFactoryDiscovery
from xtr_notifier.transport import transport_factory_discovery as module

_GROUP = TransportFactoryDiscovery.CHATTER_GROUP


def _advertise(monkeypatch: pytest.MonkeyPatch, **entries: str) -> None:
    """Make ``entries`` (scheme to ``module:attribute``) the only ones advertised."""
    advertised = [EntryPoint(scheme, value, _GROUP) for scheme, value in entries.items()]

    def entry_points(*, group: str, name: str | None = None) -> list[EntryPoint]:
        return [e for e in advertised if e.group == group and name in {None, e.name}]

    monkeypatch.setattr(module, "entry_points", entry_points)


@pytest.mark.parametrize(
    ("group", "name"),
    [
        (TransportFactoryDiscovery.CHATTER_GROUP, "chatter"),
        (TransportFactoryDiscovery.TEXTER_GROUP, "texter"),
    ],
)
def test_this_package_advertises_the_null_factory_in_both_groups(group: str, name: str) -> None:
    discovery = TransportFactoryDiscovery(group)

    assert discovery.name == name
    assert "null" in discovery.advertised_schemes()
    assert isinstance(discovery.factory_for(Dsn("null://null")), NullTransportFactory)


def test_a_group_of_its_own_is_named_after_itself() -> None:
    assert TransportFactoryDiscovery("my.factories").name == "my.factories"


def test_it_finds_no_factory_for_a_scheme_nobody_advertises() -> None:
    assert TransportFactoryDiscovery(_GROUP).factory_for(Dsn("nobody://default")) is None


def test_it_builds_the_advertised_class_with_the_client_and_the_dispatcher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _advertise(monkeypatch, dummy="tests.support.dummy_transport_factory:DummyTransportFactory")
    client = MockHttpClient()
    dispatcher = EventDispatcher()

    factory = TransportFactoryDiscovery(
        _GROUP, http_client=client, event_dispatcher=dispatcher
    ).factory_for(Dsn("dummy://host"))

    assert isinstance(factory, DummyTransportFactory)
    assert factory._http_client is client
    assert factory._event_dispatcher is dispatcher


def test_it_lists_the_advertised_schemes_sorted(monkeypatch: pytest.MonkeyPatch) -> None:
    _advertise(monkeypatch, zeta="x:Y", alpha="x:Y")

    assert TransportFactoryDiscovery(_GROUP).advertised_schemes() == ("alpha", "zeta")


def test_it_refuses_to_build_a_factory_needing_a_client_without_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _advertise(monkeypatch, dummy="tests.support.dummy_transport_factory:DummyTransportFactory")

    with pytest.raises(LogicError) as caught:
        _ = TransportFactoryDiscovery(_GROUP).factory_for(Dsn("dummy://host"))

    assert str(caught.value) == (
        'The "dummy" transport needs an HTTP client; build the transports with one.'
    )


@pytest.mark.parametrize(
    "value",
    [
        "tests.support.does_not_exist:Factory",
        "xtr_notifier.transport:Dsn",
        "xtr_notifier.transport.transport_factory_discovery:__name__",
    ],
)
def test_an_entry_that_cannot_be_loaded_or_is_no_factory_is_skipped(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    _advertise(monkeypatch, dummy=value)

    assert (
        TransportFactoryDiscovery(_GROUP, http_client=MockHttpClient()).factory_for(
            Dsn("dummy://host")
        )
        is None
    )

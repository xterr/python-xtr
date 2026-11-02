from __future__ import annotations

from importlib.metadata import EntryPoint
from typing import TYPE_CHECKING

import pytest
from typing_extensions import override
from xtr_event_dispatcher import EventDispatcher
from xtr_http_client import MockHttpClient
from xtr_logging_contracts import NullLogger

from tests.support.dummy_transport_factory import DummyTransportFactory
from xtr_mailer import LogicError, UnsupportedSchemeError
from xtr_mailer.transport import (
    AbstractTransportFactory,
    Dsn,
    NullTransport,
    NullTransportFactory,
    Transport,
    TransportFactoryDiscovery,
)
from xtr_mailer.transport import transport_factory_discovery as module

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_client_contracts import HttpClientInterface

_GROUP = TransportFactoryDiscovery.GROUP
_DUMMY = "tests.support.dummy_transport_factory:DummyTransportFactory"


def _advertise(monkeypatch: pytest.MonkeyPatch, **entries: str) -> None:
    """Make ``entries`` (scheme to ``module:attribute``) the only ones advertised."""
    advertised = [EntryPoint(scheme, value, _GROUP) for scheme, value in entries.items()]

    def entry_points(*, group: str, name: str | None = None) -> list[EntryPoint]:
        return [e for e in advertised if e.group == group and name in {None, e.name}]

    monkeypatch.setattr(module, "entry_points", entry_points)


def test_the_group_is_the_mailers() -> None:
    assert _GROUP == "xtr_mailer.transport_factories"


def test_this_package_advertises_the_null_factory() -> None:
    discovery = TransportFactoryDiscovery()

    assert "null" in discovery.advertised_schemes()
    assert isinstance(discovery.factory_for(Dsn("null", "null")), NullTransportFactory)


def test_it_finds_no_factory_for_a_scheme_nobody_advertises() -> None:
    assert TransportFactoryDiscovery().factory_for(Dsn("nobody", "default")) is None


def test_it_reads_the_entry_points_of_a_scheme_once(monkeypatch: pytest.MonkeyPatch) -> None:
    advertised = EntryPoint("null", "xtr_mailer.transport:NullTransportFactory", _GROUP)
    reads: list[str | None] = []

    def counting(*, group: str, name: str | None = None) -> list[EntryPoint]:
        reads.append(name)
        return [advertised] if (group, name) == (_GROUP, "null") else []

    monkeypatch.setattr(module, "entry_points", counting)
    discovery = TransportFactoryDiscovery()

    first = discovery.factory_for(Dsn("null", "a"))
    second = discovery.factory_for(Dsn("null", "b"))
    missing = [discovery.factory_for(Dsn("nobody", "a")) for _ in range(2)]

    assert first is second
    assert missing == [None, None]
    assert reads == ["null", "nobody"]


def test_it_builds_the_advertised_class_with_its_collaborators(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _advertise(monkeypatch, dummy=_DUMMY)
    dispatcher = EventDispatcher()
    client = MockHttpClient()
    logger = NullLogger()

    factory = TransportFactoryDiscovery(
        event_dispatcher=dispatcher, http_client=client, logger=logger
    ).factory_for(Dsn("dummy", "host"))

    assert isinstance(factory, DummyTransportFactory)
    assert factory._event_dispatcher is dispatcher
    assert factory._http_client is client
    assert factory._logger is logger


def test_it_lists_the_advertised_schemes_sorted(monkeypatch: pytest.MonkeyPatch) -> None:
    _advertise(monkeypatch, zeta="x:Y", alpha="x:Y")

    assert TransportFactoryDiscovery().advertised_schemes() == ("alpha", "zeta")


def test_it_builds_a_factory_needing_no_client_without_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _advertise(monkeypatch, null="xtr_mailer.transport:NullTransportFactory")

    assert isinstance(
        TransportFactoryDiscovery().factory_for(Dsn("null", "null")), NullTransportFactory
    )


def test_it_refuses_to_build_a_factory_needing_a_client_without_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _advertise(monkeypatch, dummy=_DUMMY)

    with pytest.raises(LogicError) as caught:
        _ = TransportFactoryDiscovery().factory_for(Dsn("dummy", "host"))

    assert str(caught.value) == (
        'The "dummy" transport needs an HTTP client; build the transports with one.'
    )


def test_a_factory_not_serving_the_dsn_it_is_advertised_for_is_passed_over(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _advertise(monkeypatch, other=_DUMMY)

    assert (
        TransportFactoryDiscovery(http_client=MockHttpClient()).factory_for(Dsn("other", "host"))
        is None
    )


@pytest.mark.parametrize(
    "value",
    [
        "tests.support.does_not_exist:Factory",
        "xtr_mailer.transport:Dsn",
        "xtr_mailer.transport.transport_factory_discovery:__name__",
    ],
)
def test_an_entry_that_cannot_be_loaded_or_is_no_factory_is_skipped(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    _advertise(monkeypatch, dummy=value)

    discovery = TransportFactoryDiscovery(http_client=MockHttpClient())

    assert discovery.factory_for(Dsn("dummy", "host")) is None


def test_an_entry_naming_a_missing_class_reads_as_an_unsupported_scheme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _advertise(monkeypatch, dummy="tests.support.dummy_transport_factory:Missing")
    builder = Transport(discovery=TransportFactoryDiscovery(http_client=MockHttpClient()))

    with pytest.raises(UnsupportedSchemeError) as caught:
        _ = builder.from_string("dummy://user:s3cret@host")

    assert str(caught.value) == 'The "dummy" scheme is not supported.'
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


class LoggerlessTransportFactory(AbstractTransportFactory):
    def __init__(
        self,
        event_dispatcher: EventDispatcherInterface | None = None,
        http_client: HttpClientInterface | None = None,
    ) -> None:
        super().__init__(event_dispatcher, http_client)

    @override
    def create(self, dsn: Dsn) -> NullTransport:
        return NullTransport()

    @override
    def _get_supported_schemes(self) -> Sequence[str]:
        return ("dummy",)


@pytest.mark.parametrize("http_client", [None, MockHttpClient()], ids=["no client", "client"])
def test_a_factory_refusing_the_discovery_keywords_is_named_for_what_it_refuses(
    monkeypatch: pytest.MonkeyPatch, http_client: MockHttpClient | None
) -> None:
    _advertise(monkeypatch, dummy=f"{__name__}:LoggerlessTransportFactory")

    with pytest.raises(LogicError) as caught:
        _ = TransportFactoryDiscovery(http_client=http_client).factory_for(Dsn("dummy", "host"))

    assert str(caught.value) == (
        'The "dummy" transport factory cannot be built with the keywords "event_dispatcher", '
        '"http_client" and "logger".'
    )
    assert caught.value.__context__ is None

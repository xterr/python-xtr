"""Building transports from DSN strings: the builder's cases, and its use of discovery."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_event_dispatcher import EventDispatcher
from xtr_http_client import MockHttpClient
from xtr_logging_contracts import NullLogger
from xtr_rate_limiter import InMemoryStorage, LimiterConfig, RateLimiterFactory

from tests.support.dummy_transport import DummyTransport
from tests.support.dummy_transport_factory import DummyTransportFactory
from tests.support.fake_transport import FakeTransport
from xtr_mailer import InvalidArgumentError, UnsupportedSchemeError
from xtr_mailer.transport import (
    Dsn,
    FailoverTransport,
    NullTransport,
    RoundRobinTransport,
    Transport,
    TransportFactoryDiscovery,
    Transports,
)

if TYPE_CHECKING:
    from xtr_mailer.transport import TransportInterface

#: What a transport tree reads as: a dummy transport by its host, a group by its kind, its
#: retry period and its members — the structure the upstream cases compare.
Shape = tuple[object, ...]


def shape(transport: TransportInterface) -> Shape:
    if isinstance(transport, DummyTransport):
        return ("dummy", transport.host)
    assert isinstance(transport, RoundRobinTransport)
    members = tuple(shape(member) for member in transport._transports)
    return (type(transport).__name__, transport._retry_period, members)


def _builder() -> Transport:
    return Transport([DummyTransportFactory(http_client=MockHttpClient())])


_A = ("dummy", "a")
_B = ("dummy", "b")


@pytest.mark.parametrize(
    ("dsn", "expected"),
    [
        pytest.param("dummy://a", _A, id="simple transport"),
        pytest.param(
            "failover(dummy://a dummy://b)", ("FailoverTransport", 60, (_A, _B)), id="failover"
        ),
        pytest.param(
            "roundrobin(dummy://a dummy://b)",
            ("RoundRobinTransport", 60, (_A, _B)),
            id="round robin",
        ),
        pytest.param(
            "roundrobin(dummy://a failover(dummy://b dummy://a) dummy://b)",
            ("RoundRobinTransport", 60, (_A, ("FailoverTransport", 60, (_B, _A)), _B)),
            id="mixed",
        ),
        pytest.param(
            "roundrobin(dummy://a dummy://b)?retry_period=15",
            ("RoundRobinTransport", 15, (_A, _B)),
            id="round robin with retry period",
        ),
    ],
)
def test_it_builds_from_a_string(dsn: str, expected: Shape) -> None:
    assert shape(_builder().from_string(dsn)) == expected


def test_from_dsn_builds_through_the_discovered_factories() -> None:
    dispatcher = EventDispatcher()
    logger = NullLogger()

    transport = Transport.from_dsn("failover(null://a null://b)", dispatcher, None, logger)

    assert isinstance(transport, FailoverTransport)
    members = transport._transports
    assert [type(member) for member in members] == [NullTransport, NullTransport]
    for member in members:
        assert isinstance(member, NullTransport)
        assert member._event_dispatcher is dispatcher
        assert member._logger is logger


def test_from_dsns_builds_a_transport_per_name() -> None:
    transports = Transport.from_dsns({"main": "null://null", "spare": "null://null"})

    assert isinstance(transports, Transports)
    assert str(transports) == "[main,spare]"


@pytest.mark.parametrize(
    ("dsn", "message"),
    [
        pytest.param(
            "dummy://a some garbage here",
            "The mailer DSN has some garbage at the end.",
            id="garbage at the end",
        ),
        pytest.param(
            "something not a dsn", "The mailer DSN must contain a scheme.", id="not a valid DSN"
        ),
        pytest.param(
            "failover(dummy://a",
            "The mailer DSN must contain a scheme.",
            id="failover not closed",
        ),
        pytest.param(
            "foobar(dummy://a)",
            'The "foobar" keyword is not valid (valid ones are "failover", "roundrobin").',
            id="not a valid keyword",
        ),
    ],
)
def test_it_refuses_a_wrong_string(dsn: str, message: str) -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = _builder().from_string(dsn)

    assert str(caught.value) == message


class _FakeTransportFactory:
    def __init__(self) -> None:
        self.built: dict[str, FakeTransport] = {}

    def create(self, dsn: Dsn) -> FakeTransport:
        self.built[dsn.host] = FakeTransport()
        return self.built[dsn.host]

    def supports(self, dsn: Dsn) -> bool:
        return dsn.scheme == "dummy"


def test_it_sets_the_rate_limiter_named_after_a_transport() -> None:
    limiter = RateLimiterFactory(
        "mailer", LimiterConfig("fixed_window", limit=1, interval="1 hour"), InMemoryStorage()
    )
    factory = _FakeTransportFactory()

    _ = Transport([factory], rate_limiter_factories={"foobar": limiter}).from_strings(
        {"foobar": "dummy://a", "moobar": "dummy://b"}
    )

    assert factory.built["a"]._rate_limiter_factory is limiter
    assert factory.built["b"]._rate_limiter_factory is None


def test_a_rate_limiter_is_not_set_on_a_transport_that_takes_none() -> None:
    limiter = RateLimiterFactory(
        "mailer", LimiterConfig("fixed_window", limit=1, interval="1 hour"), InMemoryStorage()
    )

    transport = _builder().from_string("dummy://a", limiter)

    assert isinstance(transport, DummyTransport)


def test_a_factory_given_wins_over_a_discovered_one() -> None:
    builder = Transport(
        [DummyTransportFactory(http_client=MockHttpClient())], TransportFactoryDiscovery()
    )

    assert isinstance(builder.from_string("dummy://a"), DummyTransport)
    assert isinstance(builder.from_string("null://null"), NullTransport)


def test_it_builds_from_a_parsed_dsn() -> None:
    transport = _builder().from_dsn_object(Dsn("dummy", "a"))

    assert shape(transport) == _A


def test_it_refuses_a_scheme_nothing_serves_naming_only_the_scheme() -> None:
    builder = Transport(discovery=TransportFactoryDiscovery())

    with pytest.raises(UnsupportedSchemeError) as caught:
        _ = builder.from_string("other://user:s3cret@default")

    assert str(caught.value) == 'The "other" scheme is not supported.'


def test_it_names_the_extra_to_install_for_a_known_provider() -> None:
    with pytest.raises(UnsupportedSchemeError) as caught:
        _ = Transport.from_dsn("mailgun+api://KEY:DOMAIN@default")

    assert str(caught.value) == (
        'Unable to send emails via "mailgun" as the bridge is not installed. '
        'Try running: uv add "xtr-mailer[mailgun]".'
    )
    assert "KEY" not in str(caught.value)
    assert "DOMAIN" not in str(caught.value)

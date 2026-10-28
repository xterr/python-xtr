from __future__ import annotations

import pytest
from xtr_event_dispatcher import EventDispatcher
from xtr_http_client import MockHttpClient

from tests.support.dummy_transport_factory import DummyTransportFactory
from xtr_notifier.exception import IncompleteDsnError, InvalidArgumentError
from xtr_notifier.transport import Dsn


def _factory() -> DummyTransportFactory:
    return DummyTransportFactory(MockHttpClient())


def test_it_keeps_the_http_client_and_the_event_dispatcher_for_subclasses() -> None:
    client = MockHttpClient()
    dispatcher = EventDispatcher()

    factory = DummyTransportFactory(client, dispatcher)

    assert factory._http_client is client
    assert factory._event_dispatcher is dispatcher
    assert DummyTransportFactory(client)._event_dispatcher is None


def test_it_supports_a_dsn_with_one_of_its_schemes() -> None:
    assert _factory().supports(Dsn("dummy://host"))
    assert not _factory().supports(Dsn("Dummy://host"))
    assert not _factory().supports(Dsn("other://host"))


@pytest.mark.parametrize(
    ("dsn", "expected"),
    [
        ("dummy://host.test", None),
        ("dummy://host.test?ssl=true", True),
        ("dummy://host.test?ssl=on", True),
        ("dummy://host.test?ssl=1", True),
        ("dummy://host.test?ssl=false", False),
        ("dummy://host.test?ssl=off", False),
        ("dummy://host.test?ssl=0", False),
        ("dummy://host.test?ssl=", False),
    ],
)
def test_it_reads_the_ssl_option(dsn: str, expected: bool | None) -> None:
    assert _factory().exposed_ssl(Dsn(dsn)) is expected


def test_it_refuses_an_ssl_option_that_is_not_a_boolean() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = _factory().exposed_ssl(Dsn("dummy://host.test?ssl=maybe"))


def test_it_reads_the_user_and_the_password() -> None:
    dsn = Dsn("dummy://us%40er:pa%3Ass@host.test")

    assert _factory().exposed_user(dsn) == "us@er"
    assert _factory().exposed_password(dsn) == "pa:ss"


def test_it_refuses_a_dsn_without_a_user() -> None:
    with pytest.raises(IncompleteDsnError) as caught:
        _ = _factory().exposed_user(Dsn("dummy://host.test"))

    assert str(caught.value) == 'Invalid "dummy://host.test" notifier DSN: User is not set.'


def test_it_refuses_a_dsn_without_a_password_and_never_shows_the_user() -> None:
    with pytest.raises(IncompleteDsnError) as caught:
        _ = _factory().exposed_password(Dsn("dummy://s3cr3t@host.test"))

    assert str(caught.value) == 'Invalid "dummy://host.test" notifier DSN: Password is not set.'

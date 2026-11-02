"""The factory base, driven over the checks every provider factory answers to.

Each test is one of the factory checks — supports, create, unsupported scheme, incomplete DSN —
run against a factory built on the base the way a provider library builds one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override
from xtr_event_dispatcher import EventDispatcher
from xtr_http_client import MockHttpClient
from xtr_logging_contracts import NullLogger

from tests.support.dummy_transport import DummyTransport
from xtr_mailer import IncompleteDsnError, UnsupportedSchemeError
from xtr_mailer.transport import AbstractTransportFactory, Dsn, TransportFactoryInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

_USER = "u$er"
_PASSWORD = "pa$s"


@final
class _ExampleTransportFactory(AbstractTransportFactory):
    @override
    def create(self, dsn: Dsn) -> DummyTransport:
        if not self.supports(dsn):
            raise UnsupportedSchemeError(dsn.scheme, "example", self._get_supported_schemes())
        return DummyTransport(f"{self._get_user(dsn)}/{self._get_password(dsn)}@{dsn.host}")

    @override
    def _get_supported_schemes(self) -> Sequence[str]:
        return ("example", "example+api")


def test_it_is_a_transport_factory() -> None:
    assert isinstance(_ExampleTransportFactory(), TransportFactoryInterface)


@pytest.mark.parametrize(
    ("dsn", "supported"),
    [
        (Dsn("example", "default"), True),
        (Dsn("example+api", "default"), True),
        (Dsn("example+smtp", "default"), False),
        (Dsn("EXAMPLE", "default"), False),
    ],
)
def test_it_supports_the_schemes_it_lists(dsn: Dsn, supported: bool) -> None:
    assert _ExampleTransportFactory().supports(dsn) is supported


def test_it_creates_the_transport_from_the_credentials() -> None:
    transport = _ExampleTransportFactory().create(
        Dsn("example+api", "example.com", _USER, _PASSWORD)
    )

    assert transport.host == f"{_USER}/{_PASSWORD}@example.com"


def test_it_refuses_a_scheme_it_does_not_list() -> None:
    with pytest.raises(UnsupportedSchemeError) as caught:
        _ = _ExampleTransportFactory().create(Dsn("other", "default", _USER, _PASSWORD))

    assert str(caught.value) == (
        'The "other" scheme is not supported; supported schemes for mailer "example" are: '
        '"example", "example+api".'
    )


@pytest.mark.parametrize(
    ("dsn", "message"),
    [
        (Dsn("example", "default"), "User is not set."),
        (Dsn("example", "default", password=_PASSWORD), "User is not set."),
        (Dsn("example", "default", _USER), "Password is not set."),
    ],
)
def test_it_refuses_a_dsn_missing_a_credential(dsn: Dsn, message: str) -> None:
    with pytest.raises(IncompleteDsnError) as caught:
        _ = _ExampleTransportFactory().create(dsn)

    assert str(caught.value) == message


def test_an_incomplete_dsn_error_never_shows_the_credential_it_has() -> None:
    with pytest.raises(IncompleteDsnError) as caught:
        _ = _ExampleTransportFactory().create(Dsn("example", "default", password=_PASSWORD))

    assert _PASSWORD not in str(caught.value)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_it_keeps_the_collaborators_it_hands_its_transports() -> None:
    dispatcher = EventDispatcher()
    client = MockHttpClient()
    logger = NullLogger()

    factory = _ExampleTransportFactory(dispatcher, client, logger)

    assert factory._event_dispatcher is dispatcher
    assert factory._http_client is client
    assert factory._logger is logger


def test_every_collaborator_is_optional() -> None:
    factory = _ExampleTransportFactory()

    assert (factory._event_dispatcher, factory._http_client, factory._logger) == (None, None, None)

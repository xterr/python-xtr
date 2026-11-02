from __future__ import annotations

import pytest
from xtr_event_dispatcher import EventDispatcher
from xtr_http_client import MockHttpClient
from xtr_logging_contracts import NullLogger

from xtr_mailer import UnsupportedSchemeError
from xtr_mailer.transport import (
    Dsn,
    NullTransport,
    NullTransportFactory,
    TransportFactoryInterface,
)


def _factory() -> NullTransportFactory:
    return NullTransportFactory(None, MockHttpClient(), NullLogger())


def test_it_is_a_transport_factory() -> None:
    assert isinstance(_factory(), TransportFactoryInterface)


def test_it_supports_the_null_scheme() -> None:
    assert _factory().supports(Dsn("null", ""))


def test_it_supports_no_other_scheme() -> None:
    assert not _factory().supports(Dsn("smtp", "localhost"))


def test_it_creates_a_null_transport() -> None:
    assert isinstance(_factory().create(Dsn("null", "null")), NullTransport)


def test_the_transport_gets_the_factory_dispatcher_and_logger() -> None:
    dispatcher = EventDispatcher()
    logger = NullLogger()

    transport = NullTransportFactory(dispatcher, logger=logger).create(
        Dsn.from_string("null://null")
    )

    assert transport._event_dispatcher is dispatcher
    assert transport._logger is logger


def test_it_refuses_another_scheme() -> None:
    with pytest.raises(UnsupportedSchemeError) as caught:
        _ = _factory().create(Dsn("smtp", "localhost"))

    assert str(caught.value) == (
        'The "smtp" scheme is not supported; supported schemes for mailer "null" are: "null".'
    )


def test_the_refusal_never_shows_credentials() -> None:
    with pytest.raises(UnsupportedSchemeError) as caught:
        _ = _factory().create(Dsn.from_string("smtp://user:s3cret@localhost"))

    assert "s3cret" not in str(caught.value)
    assert "user" not in str(caught.value)

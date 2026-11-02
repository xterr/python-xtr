from __future__ import annotations

import pytest
from xtr_event_dispatcher import EventDispatcher
from xtr_http_client import MockHttpClient
from xtr_logging_contracts import NullLogger

from xtr_mailer import InvalidArgumentError, UnsupportedSchemeError
from xtr_mailer.transport import (
    Dsn,
    SendmailTransport,
    SendmailTransportFactory,
    Transport,
    TransportFactoryInterface,
)


def _factory() -> SendmailTransportFactory:
    return SendmailTransportFactory(None, MockHttpClient(), NullLogger())


def test_it_is_a_transport_factory() -> None:
    assert isinstance(_factory(), TransportFactoryInterface)


@pytest.mark.parametrize(
    ("dsn", "supported"),
    [
        (Dsn("sendmail+smtp", "default"), True),
        (Dsn("sendmail", "default"), True),
        (Dsn("sendmail+http", "default"), False),
    ],
)
def test_it_supports_the_sendmail_schemes(dsn: Dsn, supported: bool) -> None:
    assert _factory().supports(dsn) is supported


def test_it_creates_a_sendmail_transport_in_smtp_mode_by_default() -> None:
    transport = _factory().create(Dsn("sendmail+smtp", "default"))

    assert isinstance(transport, SendmailTransport)
    assert transport._command == "/usr/sbin/sendmail -bs"


def test_the_command_option_picks_the_command() -> None:
    dsn = Dsn("sendmail+smtp", "default", options={"command": "/usr/sbin/sendmail -oi -t"})

    transport = _factory().create(dsn)

    assert transport._command == "/usr/sbin/sendmail -oi -t"


def test_a_command_read_from_a_dsn_string_is_decoded() -> None:
    dsn = Dsn.from_string("sendmail://default?command=/usr/sbin/sendmail%20-oi%20-t")

    assert _factory().create(dsn)._command == "/usr/sbin/sendmail -oi -t"


@pytest.mark.parametrize("option", ["command[]=a", "command[x]=a"])
def test_a_command_that_is_not_one_string_is_refused(option: str) -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = _factory().create(Dsn.from_string(f"sendmail://default?{option}"))

    assert str(caught.value) == 'The "command" option is not valid: it must be a sendmail command.'


def test_the_transport_gets_the_factory_dispatcher_and_logger() -> None:
    dispatcher = EventDispatcher()
    logger = NullLogger()

    transport = SendmailTransportFactory(dispatcher, logger=logger).create(
        Dsn("sendmail", "default", options={"command": "/usr/sbin/sendmail -t"})
    )

    assert transport._event_dispatcher is dispatcher
    assert transport._logger is logger


def test_it_refuses_another_scheme() -> None:
    with pytest.raises(UnsupportedSchemeError) as caught:
        _ = _factory().create(Dsn("sendmail+http", "default"))

    assert str(caught.value) == (
        'The "sendmail+http" scheme is not supported; supported schemes for mailer "sendmail" '
        'are: "sendmail", "sendmail+smtp".'
    )


@pytest.mark.parametrize("scheme", ["sendmail", "sendmail+smtp"])
def test_a_sendmail_dsn_finds_this_factory(scheme: str) -> None:
    transport = Transport.from_dsn(f"{scheme}://default")

    assert isinstance(transport, SendmailTransport)

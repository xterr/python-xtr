from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_event_dispatcher import EventDispatcher
from xtr_http_client import MockHttpClient
from xtr_logging_contracts import NullLogger

from xtr_mailer import InvalidArgumentError
from xtr_mailer.testing import FactoryCases, assert_factory_cases
from xtr_mailer.transport import (
    Dsn,
    SendmailTransport,
    SendmailTransportFactory,
    Transport,
    TransportFactoryInterface,
)

if TYPE_CHECKING:
    from xtr_mailer.transport import TransportInterface


def _factory() -> SendmailTransportFactory:
    return SendmailTransportFactory(None, MockHttpClient(), NullLogger())


def _command_of(transport: TransportInterface) -> str:
    """What two sendmail transports built alike agree on: the command they run."""
    assert isinstance(transport, SendmailTransport)
    return transport._command


def test_it_is_a_transport_factory() -> None:
    assert isinstance(_factory(), TransportFactoryInterface)


def test_it_does_what_every_factory_owes() -> None:
    command = "/usr/sbin/sendmail -oi -t"
    piped = SendmailTransport(command, logger=NullLogger())
    # A command read from a DSN string is decoded.
    encoded = Dsn.from_string("sendmail://default?command=/usr/sbin/sendmail%20-oi%20-t")

    assert_factory_cases(
        FactoryCases(
            create_factory=_factory,
            supports=[
                (Dsn("sendmail+smtp", "default"), True),
                (Dsn("sendmail", "default"), True),
                (Dsn("sendmail+http", "default"), False),
            ],
            create=[
                (
                    Dsn("sendmail+smtp", "default"),
                    SendmailTransport("/usr/sbin/sendmail -bs", logger=NullLogger()),
                ),
                (Dsn("sendmail+smtp", "default", options={"command": command}), piped),
                (encoded, piped),
            ],
            unsupported_scheme=[
                (
                    Dsn("sendmail+http", "default"),
                    (
                        'The "sendmail+http" scheme is not supported; supported schemes for '
                        'mailer "sendmail" are: "sendmail", "sendmail+smtp".'
                    ),
                )
            ],
            read_state=_command_of,
        )
    )


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


@pytest.mark.parametrize("scheme", ["sendmail", "sendmail+smtp"])
def test_a_sendmail_dsn_finds_this_factory(scheme: str) -> None:
    transport = Transport.from_dsn(f"{scheme}://default")

    assert isinstance(transport, SendmailTransport)

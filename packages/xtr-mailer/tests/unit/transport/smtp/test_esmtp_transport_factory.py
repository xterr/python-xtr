"""EsmtpTransportFactory: the upstream factory cases, then what it hands the transport on."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_event_dispatcher import EventDispatcher
from xtr_http_client import MockHttpClient
from xtr_logging_contracts import NullLogger

from tests.support.esmtp_state import esmtp_state
from tests.support.scripted_smtp_server import ScriptedSmtpServer
from xtr_mailer.exception import InvalidArgumentError
from xtr_mailer.testing import PASSWORD, USER, FactoryCases, assert_factory_cases
from xtr_mailer.transport import Dsn, TransportFactoryInterface
from xtr_mailer.transport.smtp import EsmtpTransport, EsmtpTransportFactory

if TYPE_CHECKING:
    from collections.abc import Callable

FINGERPRINT = "6A1CF3B08D175A284C30BC10DE19162307C7286E"


def _factory() -> EsmtpTransportFactory:
    return EsmtpTransportFactory(None, MockHttpClient(), NullLogger())


def _smtps(configure: Callable[[EsmtpTransport], object] = lambda _: None) -> EsmtpTransport:
    transport = EsmtpTransport("example.com", 465, True, logger=NullLogger())
    _ = configure(transport)
    return transport


def _smtp(port: int = 25) -> EsmtpTransport:
    return EsmtpTransport("example.com", port, False, logger=NullLogger())


def test_it_is_a_transport_factory() -> None:
    assert isinstance(_factory(), TransportFactoryInterface)


_VERIFY_PEER_OFF = _smtps(lambda transport: transport.set_verify_peer(False))
_PINNED = _smtps(lambda transport: transport.set_peer_fingerprint(FINGERPRINT))
_AUTO_TLS_OFF = _smtp().set_auto_tls(False)
_TLS_REQUIRED = _smtps(lambda transport: transport.set_require_tls(True))
_CREATE: list[tuple[Dsn, EsmtpTransport]] = [
    (Dsn("smtp", "localhost"), EsmtpTransport("localhost", 25, False, logger=NullLogger())),
    (
        Dsn("smtps", "example.com", USER, PASSWORD, 99),
        EsmtpTransport("example.com", 99, True, logger=NullLogger())
        .set_username(USER)
        .set_password(PASSWORD),
    ),
    (Dsn("smtps", "example.com"), _smtps()),
    (Dsn("smtps", "example.com", "", "", 465), _smtps()),
    # Upstream's boolean `false` option is written "false" here: options hold strings.
    (Dsn("smtps", "example.com", "", "", 465, {"verify_peer": "false"}), _VERIFY_PEER_OFF),
    (Dsn.from_string("smtps://:@example.com?verify_peer=0"), _VERIFY_PEER_OFF),
    (Dsn.from_string("smtps://:@example.com?verify_peer="), _smtps()),
    (Dsn("smtps", "example.com", "", "", 465, {"peer_fingerprint": FINGERPRINT}), _PINNED),
    (Dsn.from_string(f"smtps://:@example.com?peer_fingerprint={FINGERPRINT}"), _PINNED),
    (
        Dsn("smtps", "example.com", "", "", 465, {"local_domain": "example.com"}),
        _smtps(lambda transport: transport.set_local_domain("example.com")),
    ),
    (
        Dsn("smtps", "example.com", "", "", 465, {"max_per_second": "2"}),
        _smtps(lambda transport: transport.set_max_per_second(2.0)),
    ),
    (
        Dsn(
            "smtps",
            "example.com",
            "",
            "",
            465,
            {"restart_threshold": "10", "restart_threshold_sleep": "1"},
        ),
        _smtps(lambda transport: transport.set_restart_threshold(10, 1)),
    ),
    (
        Dsn("smtps", "example.com", "", "", 465, {"ping_threshold": "10"}),
        _smtps(lambda transport: transport.set_ping_threshold(10)),
    ),
    (
        Dsn.from_string("smtps://:@example.com:465?timeout=10"),
        _smtps(lambda transport: transport.set_timeout(10.0)),
    ),
    (Dsn.from_string("smtp://:@example.com:25?timeout=2.5"), _smtp().set_timeout(2.5)),
    (Dsn("smtp", "example.com", "", "", 25, {"auto_tls": "false"}), _AUTO_TLS_OFF),
    (Dsn("smtp", "example.com", "", "", 0, {"auto_tls": "false"}), _AUTO_TLS_OFF),
    (Dsn.from_string("smtp://:@example.com?auto_tls=false"), _AUTO_TLS_OFF),
    (
        Dsn.from_string("smtp://:@example.com:465?auto_tls=false"),
        _smtp(465).set_auto_tls(False),
    ),
    (
        Dsn.from_string("smtps://:@example.com:465?source_ip=0.0.0.0"),
        _smtps(lambda transport: transport.set_source_ip("0.0.0.0")),  # noqa: S104 - not a bind, a value read back
    ),
    (
        Dsn.from_string("smtps://:@example.com:465?source_ip=[2606:4700:20::681a:5fb]"),
        _smtps(lambda transport: transport.set_source_ip("[2606:4700:20::681a:5fb]")),
    ),
    (Dsn("smtps", "example.com", "", "", 465, {"require_tls": "true"}), _TLS_REQUIRED),
    (Dsn.from_string("smtps://:@example.com?require_tls=true"), _TLS_REQUIRED),
]


def test_it_does_what_every_factory_owes() -> None:
    assert_factory_cases(
        FactoryCases(
            create_factory=_factory,
            supports=[
                (Dsn("smtp", "example.com"), True),
                (Dsn("smtps", "example.com"), True),
                (Dsn("api", "example.com"), False),
            ],
            create=_CREATE,
            unsupported_scheme=[
                (
                    Dsn("null", ""),
                    (
                        'The "null" scheme is not supported; supported schemes for mailer "smtp" '
                        'are: "smtp", "smtps".'
                    ),
                )
            ],
            read_state=esmtp_state,
        )
    )


def test_a_dsn_with_no_port_to_another_host_speaks_tls_on_465() -> None:
    transport = _factory().create(Dsn.from_string("smtp://example.com"))

    assert esmtp_state(transport) == esmtp_state(EsmtpTransport("example.com", logger=NullLogger()))
    assert (transport._config.port, transport._config.tls) == (465, True)
    assert transport.is_auto_tls()


def test_a_dsn_with_a_port_starts_plain_and_switches_to_tls_when_offered() -> None:
    transport = _factory().create(Dsn.from_string("smtp://example.com:587"))

    assert (transport._config.port, transport._config.tls) == (587, False)
    assert transport.is_auto_tls()


@pytest.mark.parametrize("timeout", ["0", "-1", "abc"])
def test_it_refuses_a_timeout_that_is_not_a_positive_number(timeout: str) -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = _factory().create(Dsn.from_string(f"smtp://example.com?timeout={timeout}"))

    assert str(caught.value) == (
        'The "timeout" option is not valid: it must be a positive number of seconds, '
        f'"{timeout}" given.'
    )


def test_the_transport_gets_the_factory_dispatcher_and_logger() -> None:
    dispatcher = EventDispatcher()
    logger = NullLogger()

    transport = EsmtpTransportFactory(dispatcher, logger=logger).create(Dsn("smtp", "localhost"))

    assert transport._event_dispatcher is dispatcher
    assert transport._logger is logger


def test_the_credentials_are_decoded_once() -> None:
    transport = _factory().create(Dsn.from_string("smtp://u%2540%40:p%2525%3A%40@localhost"))

    assert (transport.get_username(), transport.get_password()) == ("u%40@", "p%25:@")


def test_the_restart_sleep_defaults_to_zero() -> None:
    transport = _factory().create(Dsn.from_string("smtp://localhost?restart_threshold=5"))

    assert (transport._restart_threshold, transport._restart_threshold_sleep) == (5, 0)


@pytest.mark.anyio
async def test_the_connection_leaves_from_the_source_ip() -> None:
    async with ScriptedSmtpServer() as server:
        transport = _factory().create(
            Dsn.from_string(f"smtp://127.0.0.1:{server.port}?source_ip=127.0.0.1&timeout=2")
        )

        await transport.start()
        await transport.stop()

    assert server.peers == ["127.0.0.1"]

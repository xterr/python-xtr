from __future__ import annotations

import pytest
from xtr_http_client import MockHttpClient
from xtr_notifier.exception import IncompleteDsnError, UnsupportedSchemeError
from xtr_notifier.testing import FactoryCases, assert_factory_cases
from xtr_notifier.transport import Dsn

from xtr_telegram_notifier import TelegramTransport, TelegramTransportFactory


def _factory() -> TelegramTransportFactory:
    return TelegramTransportFactory(MockHttpClient())


def test_it_does_what_every_factory_owes() -> None:
    assert_factory_cases(
        FactoryCases(
            create_factory=_factory,
            supports=[
                (True, "telegram://host?channel=testChannel"),
                (False, "somethingElse://host?channel=testChannel"),
            ],
            create=[
                (
                    "telegram://host.test?channel=testChannel",
                    "telegram://user:password@host.test?channel=testChannel",
                ),
                (
                    "telegram://host.test?channel=testChannel&ssl=false",
                    "telegram://user:password@host.test?channel=testChannel&sslmode=disable",
                ),
                (
                    "telegram://host.test?channel=testChannel&ssl=false",
                    "telegram://user:password@host.test?channel=testChannel&ssl=false",
                ),
                (
                    "telegram://host.test?channel=testChannel",
                    "telegram://user:password@host.test?channel=testChannel&ssl=true",
                ),
                ("telegram://api.telegram.org", "telegram://user:password@default"),
                ("telegram://host.test:8443", "telegram://user:password@host.test:8443"),
            ],
            unsupported_scheme=[("somethingElse://user:pwd@host", '"somethingElse" scheme')],
            incomplete_dsn=[
                (
                    "telegram://token@host.test?channel=testChannel",
                    'Invalid "telegram://host.test" notifier DSN: Malformed token.',
                ),
                (
                    "telegram://host.test?channel=testChannel",
                    'Invalid "telegram://host.test" notifier DSN: Missing token.',
                ),
            ],
        )
    )


def test_the_ssl_option_wins_over_the_legacy_sslmode() -> None:
    transport = _factory().create(Dsn("telegram://u:p@default?ssl=true&sslmode=disable"))

    assert str(transport) == "telegram://api.telegram.org"


def test_it_builds_the_token_from_the_user_and_the_password() -> None:
    transport = _factory().create(Dsn("telegram://123456:ABC-DEF@default?channel=c"))

    assert isinstance(transport, TelegramTransport)
    assert transport._token == "123456:ABC-DEF"


def test_an_incomplete_dsn_never_shows_the_token() -> None:
    with pytest.raises(IncompleteDsnError) as raised:
        _ = _factory().create(Dsn("telegram://SECRET@default"))

    assert "SECRET" not in str(raised.value)


def test_an_unsupported_scheme_never_shows_the_credentials() -> None:
    with pytest.raises(UnsupportedSchemeError) as raised:
        _ = _factory().create(Dsn("other://USER:SECRET@default"))

    assert "SECRET" not in str(raised.value)
    assert "USER" not in str(raised.value)

from __future__ import annotations

import pytest
from xtr_http_client import MockHttpClient
from xtr_notifier.exception import InvalidArgumentError, UnsupportedSchemeError
from xtr_notifier.testing import FactoryCases, assert_factory_cases
from xtr_notifier.transport import Dsn

from xtr_slack_notifier import SlackTransportFactory


def _factory() -> SlackTransportFactory:
    return SlackTransportFactory(MockHttpClient())


def test_it_does_what_every_factory_owes() -> None:
    assert_factory_cases(
        FactoryCases(
            create_factory=_factory,
            supports=[
                (True, "slack://xoxb-TestToken@host?channel=testChannel"),
                (False, "somethingElse://xoxb-TestToken@host?channel=testChannel"),
            ],
            create=[
                ("slack://host.test", "slack://xoxb-TestToken@host.test"),
                (
                    "slack://host.test?channel=testChannel",
                    "slack://xoxb-TestToken@host.test/?channel=testChannel",
                ),
                (
                    "slack://host.test?channel=testChannel",
                    "slack://xoxb-TestToken@host.test?channel=testChannel",
                ),
                ("slack://slack.com?channel=C1", "slack://xoxb-TestToken@default?channel=C1"),
                ("slack://host.test:8443", "slack://xoxb-TestToken@host.test:8443"),
            ],
            unsupported_scheme=[("somethingElse://xoxb-TestToken@host?channel=testChannel", None)],
            incomplete_dsn=[("slack://host.test?channel=testChannel", "User is not set.")],
        )
    )


def test_the_ssl_option_reaches_the_host_over_http() -> None:
    transport = _factory().create(Dsn("slack://xoxb-T@host.test?ssl=false"))

    assert transport._get_http_scheme() == "http"


def test_a_token_of_another_kind_is_refused_when_built() -> None:
    with pytest.raises(InvalidArgumentError, match='needs to start with "xoxb-"'):
        _ = _factory().create(Dsn("slack://SECRET@default"))


def test_an_unsupported_scheme_never_shows_the_token() -> None:
    with pytest.raises(UnsupportedSchemeError) as raised:
        _ = _factory().create(Dsn("other://xoxb-SECRET@default"))

    assert "SECRET" not in str(raised.value)

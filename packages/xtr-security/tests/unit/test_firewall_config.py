"""A firewall configuration validates its own combinations."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_http_foundation import SessionCookieConfig
from xtr_http_foundation.exception import InvalidArgumentError

from xtr_security.bundle import AccessTokenConfig, FirewallConfig, ServiceTokenHandlerConfig
from xtr_security.exception import InvalidConfigurationError

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.anyio


class _Handler:
    """A stand-in handler class."""


def _access_token() -> AccessTokenConfig:
    return AccessTokenConfig(token_handler=ServiceTokenHandlerConfig(_Handler))


def test_an_open_firewall_needs_no_authenticator() -> None:
    firewall = FirewallConfig(pattern=r"^/docs", security=False)

    assert firewall.security is False
    assert firewall.authenticators == ()
    assert firewall.listeners == ()


def test_a_firewall_keeps_its_listener_chain_qualifiers() -> None:
    firewall = FirewallConfig(security=False, listeners=("late", "early"))

    assert firewall.listeners == ("late", "early")


def test_a_secured_firewall_needs_an_authenticator() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = FirewallConfig(pattern=r"^/api")


def test_a_firewall_configures_no_session_cookie_by_default() -> None:
    assert FirewallConfig(security=False).session_cookie is None


def test_a_stateful_firewall_keeps_the_session_cookie_it_names() -> None:
    cookie = SessionCookieConfig(name="sid", secure=True)

    firewall = FirewallConfig(security=False, stateless=False, session_cookie=cookie)

    assert firewall.session_cookie is cookie


@pytest.mark.parametrize(
    "build",
    [
        lambda: SessionCookieConfig(name=""),
        lambda: SessionCookieConfig(samesite="sometimes"),
        lambda: SessionCookieConfig(lifetime=-1),
    ],
    ids=["empty name", "unknown samesite", "negative lifetime"],
)
def test_a_session_cookie_no_browser_would_keep_is_refused(
    build: Callable[[], SessionCookieConfig],
) -> None:
    with pytest.raises(InvalidArgumentError):
        _ = build()


def test_a_stateful_firewall_is_accepted() -> None:
    firewall = FirewallConfig(pattern=r"^/api", stateless=False, authenticators=(_access_token(),))

    assert firewall.stateless is False


def test_an_empty_context_key_is_refused() -> None:
    from xtr_security_core.exception import InvalidArgumentError

    with pytest.raises(InvalidArgumentError):
        _ = FirewallConfig(
            pattern=r"^/api",
            stateless=False,
            context_key="",
            authenticators=(_access_token(),),
        )


def test_an_unknown_session_strategy_is_refused() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = FirewallConfig(
            pattern=r"^/api",
            stateless=False,
            session_strategy="rotate",
            authenticators=(_access_token(),),
        )


def test_the_session_strategy_defaults_to_a_migration() -> None:
    firewall = FirewallConfig(pattern=r"^/api", authenticators=(_access_token(),))

    assert firewall.session_strategy == "migrate"


def test_a_secured_firewall_keeps_its_authenticators() -> None:
    firewall = FirewallConfig(pattern=r"^/api", authenticators=(_access_token(),))

    assert len(firewall.authenticators) == 1


def test_a_bad_pattern_is_refused() -> None:
    from xtr_security_core.exception import InvalidArgumentError

    with pytest.raises(InvalidArgumentError):
        _ = FirewallConfig(pattern=r"[", security=False)


async def test_to_matcher_claims_requests_on_the_pattern() -> None:
    from tests.support.messages import make_message

    firewall = FirewallConfig(pattern=r"^/api", authenticators=(_access_token(),))
    matcher = firewall.to_matcher()

    assert await matcher.matches(make_message(path="/api/books")) is True
    assert await matcher.matches(make_message(path="/public")) is False


async def test_to_matcher_with_no_constraints_claims_every_request() -> None:
    from tests.support.messages import make_message

    firewall = FirewallConfig(security=False)
    matcher = firewall.to_matcher()

    assert await matcher.matches(make_message(path="/anything")) is True


async def test_to_matcher_honours_a_callable() -> None:
    from xtr_http_message_contracts import ServerRequestInterface

    from tests.support.messages import make_message

    def asks_for_ok(message: ServerRequestInterface) -> bool:
        return message.get_query_params().get("ok") == "1"

    firewall = FirewallConfig(request_matcher=asks_for_ok, security=False)
    matcher = firewall.to_matcher()

    assert await matcher.matches(make_message(query="ok=1")) is True
    assert await matcher.matches(make_message()) is False

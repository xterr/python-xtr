"""A firewall configuration validates its own combinations."""

from __future__ import annotations

import pytest

from xtr_security.bundle import AccessTokenConfig, FirewallConfig, ServiceTokenHandlerConfig
from xtr_security.exception import InvalidConfigurationError

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


def test_a_stateful_firewall_is_refused() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = FirewallConfig(pattern=r"^/api", stateless=False, authenticators=(_access_token(),))


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

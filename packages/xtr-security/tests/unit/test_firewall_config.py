"""A firewall configuration validates its own combinations."""

from __future__ import annotations

import pytest

from xtr_security.bundle import AccessTokenConfig, FirewallConfig, ServiceTokenHandlerConfig
from xtr_security.exception import InvalidConfigurationError


class _Handler:
    """A stand-in handler class."""


def _access_token() -> AccessTokenConfig:
    return AccessTokenConfig(token_handler=ServiceTokenHandlerConfig(_Handler))


def test_an_open_firewall_needs_no_authenticator() -> None:
    firewall = FirewallConfig(pattern=r"^/docs", security=False)

    assert firewall.security is False
    assert firewall.authenticators == ()


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


def test_to_matcher_claims_requests_on_the_pattern() -> None:
    from tests.support.requests import make_request

    firewall = FirewallConfig(pattern=r"^/api", authenticators=(_access_token(),))
    matcher = firewall.to_matcher()

    on_api = make_request()
    on_api.scope["path"] = "/api/books"
    elsewhere = make_request()
    elsewhere.scope["path"] = "/public"

    assert matcher.matches(on_api) is True
    assert matcher.matches(elsewhere) is False


def test_to_matcher_with_no_constraints_claims_every_request() -> None:
    from tests.support.requests import make_request

    firewall = FirewallConfig(security=False)
    matcher = firewall.to_matcher()

    request = make_request()
    request.scope["path"] = "/anything"

    assert matcher.matches(request) is True


def test_to_matcher_honours_a_callable() -> None:
    from starlette.requests import Request

    from tests.support.requests import make_request

    def wants_header(request: Request) -> bool:
        return request.headers.get("x-ok") == "1"

    firewall = FirewallConfig(request_matcher=wants_header, security=False)
    matcher = firewall.to_matcher()

    assert matcher.matches(make_request(headers={"x-ok": "1"})) is True
    assert matcher.matches(make_request()) is False

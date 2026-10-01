"""The trust resolver reads authentication strength from a token."""

from __future__ import annotations

from xtr_security_core.authentication import (
    AuthenticationTrustResolver,
    AuthenticationTrustResolverInterface,
)
from xtr_security_core.authentication.token import NullToken, UsernamePasswordToken
from xtr_security_core.user import InMemoryUser


def test_it_inherits_the_trust_resolver_interface() -> None:
    assert AuthenticationTrustResolverInterface in AuthenticationTrustResolver.__mro__


def test_none_is_not_authenticated() -> None:
    resolver = AuthenticationTrustResolver()

    assert resolver.is_authenticated(None) is False
    assert resolver.is_full_fledged(None) is False


def test_null_token_is_not_authenticated() -> None:
    resolver = AuthenticationTrustResolver()

    assert resolver.is_authenticated(NullToken()) is False
    assert resolver.is_full_fledged(NullToken()) is False


def test_a_real_token_is_authenticated_and_full_fledged() -> None:
    resolver = AuthenticationTrustResolver()
    token = UsernamePasswordToken(InMemoryUser("alice"), "api", ["ROLE_USER"])

    assert resolver.is_authenticated(token) is True
    assert resolver.is_full_fledged(token) is True

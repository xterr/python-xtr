"""The trust resolver reads authentication strength and recency from a token."""

from __future__ import annotations

from datetime import UTC, datetime

from xtr_clock import MockClock

from xtr_security_core.authentication import (
    AuthenticationMethod,
    AuthenticationTrustResolver,
    AuthenticationTrustResolverInterface,
)
from xtr_security_core.authentication.token import (
    AbstractToken,
    NullToken,
    UsernamePasswordToken,
)
from xtr_security_core.user import InMemoryUser

_NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
_NOW_TS = int(_NOW.timestamp())


def _resolver() -> AuthenticationTrustResolver:
    return AuthenticationTrustResolver(clock=MockClock(_NOW))


def _token(proofs: dict[str, int] | None = None) -> UsernamePasswordToken:
    token = UsernamePasswordToken(InMemoryUser("alice"), "api", ["ROLE_USER"])
    if proofs is not None:
        token.set_authentication_proofs(proofs)
    return token


def test_it_inherits_the_trust_resolver_interface() -> None:
    assert AuthenticationTrustResolverInterface in AuthenticationTrustResolver.__mro__


def test_none_is_not_authenticated() -> None:
    resolver = _resolver()

    assert resolver.is_authenticated(None) is False
    assert resolver.is_full_fledged(None) is False
    assert resolver.is_authenticated() is False


def test_null_token_is_not_authenticated() -> None:
    resolver = _resolver()

    assert resolver.is_authenticated(NullToken()) is False
    assert resolver.is_full_fledged(NullToken()) is False


def test_a_token_without_a_user_is_not_authenticated() -> None:
    assert _resolver().is_authenticated(AbstractToken(["ROLE_USER"])) is False


def test_a_token_with_a_user_is_authenticated_and_full_fledged() -> None:
    resolver = _resolver()
    token = _token()

    assert resolver.is_authenticated(token) is True
    assert resolver.is_full_fledged(token) is True


def test_no_token_is_remembered() -> None:
    assert _resolver().is_remember_me(_token()) is False


def test_without_proofs_nothing_is_recent() -> None:
    resolver = _resolver()

    assert resolver.is_authenticated_recently(_token()) is False
    assert resolver.is_authenticated_very_recently(_token()) is False


def test_a_proof_inside_the_recent_window_is_recent() -> None:
    token = _token({AuthenticationMethod.PASSWORD: _NOW_TS - 2 * 3600})

    assert _resolver().is_authenticated_recently(token) is True


def test_a_proof_past_the_recent_window_is_not_recent() -> None:
    token = _token({AuthenticationMethod.PASSWORD: _NOW_TS - 2 * 3600 - 1})

    assert _resolver().is_authenticated_recently(token) is False


def test_a_proof_inside_the_very_recent_window_is_very_recent() -> None:
    token = _token({AuthenticationMethod.PASSWORD: _NOW_TS - 300})

    assert _resolver().is_authenticated_very_recently(token) is True


def test_a_proof_past_the_very_recent_window_is_not_very_recent() -> None:
    token = _token({AuthenticationMethod.PASSWORD: _NOW_TS - 301})

    assert _resolver().is_authenticated_very_recently(token) is False


def test_recency_counts_from_the_last_proof() -> None:
    token = _token(
        {
            AuthenticationMethod.PASSWORD: _NOW_TS - 10_000,
            AuthenticationMethod.ONE_TIME_PASSWORD: _NOW_TS - 60,
        }
    )

    assert _resolver().is_authenticated_very_recently(token) is True


def test_the_windows_are_configurable() -> None:
    resolver = AuthenticationTrustResolver(
        recent_lifetime=10, very_recent_lifetime=5, clock=MockClock(_NOW)
    )
    token = _token({AuthenticationMethod.PASSWORD: _NOW_TS - 6})

    assert resolver.is_authenticated_recently(token) is True
    assert resolver.is_authenticated_very_recently(token) is False


def test_a_token_without_a_user_is_never_recent() -> None:
    token = AbstractToken()
    token.set_authentication_proofs({AuthenticationMethod.PASSWORD: _NOW_TS})

    assert _resolver().is_authenticated_recently(token) is False
    assert _resolver().is_authenticated_recently(None) is False


def test_it_reads_the_system_clock_by_default() -> None:
    token = _token({AuthenticationMethod.PASSWORD: int(datetime.now(UTC).timestamp())})

    assert AuthenticationTrustResolver().is_authenticated_very_recently(token) is True

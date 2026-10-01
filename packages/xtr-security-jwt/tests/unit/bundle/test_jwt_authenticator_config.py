"""The authenticator configuration is buildable with no arguments and overridable."""

from __future__ import annotations

from xtr_security_jwt.bundle.jwt_authenticator_config import JwtAuthenticatorConfig


def test_it_builds_with_no_arguments() -> None:
    config = JwtAuthenticatorConfig()

    assert config.provider is None
    assert config.authenticator is None


def test_it_carries_a_provider_and_authenticator_override() -> None:
    class _Authenticator: ...

    config = JwtAuthenticatorConfig(provider="jwt_users", authenticator=_Authenticator)

    assert config.provider == "jwt_users"
    assert config.authenticator is _Authenticator

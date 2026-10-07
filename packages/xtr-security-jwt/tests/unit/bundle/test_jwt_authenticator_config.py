"""The authenticator configuration is buildable with no arguments."""

from __future__ import annotations

from xtr_security_jwt.bundle.jwt_authenticator_config import JwtAuthenticatorConfig


def test_it_builds_with_no_arguments() -> None:
    config = JwtAuthenticatorConfig()

    assert isinstance(config, JwtAuthenticatorConfig)

"""The user-provider configuration defaults to the plain stateless JWT user."""

from __future__ import annotations

from xtr_security_jwt.bundle.jwt_user_provider_config import JwtUserProviderConfig
from xtr_security_jwt.security.user.jwt_user import JwtUser


def test_it_defaults_to_the_plain_jwt_user() -> None:
    assert JwtUserProviderConfig().user_class is JwtUser


def test_it_carries_a_custom_user_class() -> None:
    class _CustomUser: ...

    assert JwtUserProviderConfig(user_class=_CustomUser).user_class is _CustomUser

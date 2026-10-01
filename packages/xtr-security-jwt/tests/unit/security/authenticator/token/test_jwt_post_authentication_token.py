"""The post-authentication token carries the raw token and the firewall."""

from __future__ import annotations

from xtr_security_core.authentication.token.abstract_token import AbstractToken
from xtr_security_core.user.in_memory_user import InMemoryUser

from xtr_security_jwt.security.authenticator.token.jwt_post_authentication_token import (
    JwtPostAuthenticationToken,
)


def test_it_is_an_abstract_token() -> None:
    assert AbstractToken in JwtPostAuthenticationToken.__mro__


def test_it_carries_the_user_firewall_roles_and_raw_token() -> None:
    user = InMemoryUser("ada", roles=["ROLE_USER"])
    token = JwtPostAuthenticationToken(user, "api", ("ROLE_USER",), "a.b.c")

    assert token.get_user() is user
    assert token.get_firewall_name() == "api"
    assert list(token.get_role_names()) == ["ROLE_USER"]
    assert token.get_credentials() == "a.b.c"

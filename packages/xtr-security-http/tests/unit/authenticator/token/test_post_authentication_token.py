"""The post-authentication token remembers the firewall that made it."""

from __future__ import annotations

from xtr_security_core.authentication.token.token_interface import TokenInterface
from xtr_security_core.user import InMemoryUser

from xtr_security_http.authenticator.token import PostAuthenticationToken


def test_it_inherits_the_token_interface() -> None:
    assert TokenInterface in PostAuthenticationToken.__mro__


def test_it_keeps_the_firewall_user_and_roles() -> None:
    user = InMemoryUser("alice")
    token = PostAuthenticationToken(user, "api", ["ROLE_USER"])

    assert token.get_firewall_name() == "api"
    assert token.get_role_names() == ("ROLE_USER",)
    assert token.get_user() is user

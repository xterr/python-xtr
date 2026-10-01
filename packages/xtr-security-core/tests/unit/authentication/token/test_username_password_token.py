"""The username/password token names a user, its firewall and its roles."""

from __future__ import annotations

from xtr_security_core.authentication.token import AbstractToken, UsernamePasswordToken
from xtr_security_core.user import InMemoryUser


def test_it_is_an_abstract_token() -> None:
    assert AbstractToken in UsernamePasswordToken.__mro__


def test_it_carries_the_user_firewall_and_roles() -> None:
    token = UsernamePasswordToken(InMemoryUser("alice"), "api", ["ROLE_USER"])

    user = token.get_user()
    assert user is not None
    assert user.get_user_identifier() == "alice"
    assert token.get_firewall_name() == "api"
    assert token.get_role_names() == ("ROLE_USER",)


def test_its_roles_default_to_empty() -> None:
    token = UsernamePasswordToken(InMemoryUser("alice"), "worker")

    assert token.get_role_names() == ()
    assert token.get_firewall_name() == "worker"

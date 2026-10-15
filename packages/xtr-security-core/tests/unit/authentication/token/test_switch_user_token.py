"""The switch-user token carries the target user and the way back."""

from __future__ import annotations

import pytest

from xtr_security_core.authentication.token import SwitchUserToken, UsernamePasswordToken
from xtr_security_core.exception import InvalidArgumentError
from xtr_security_core.user import InMemoryUser


def _original() -> UsernamePasswordToken:
    return UsernamePasswordToken(InMemoryUser("alice"), "api", ["ROLE_USER"])


def test_it_is_a_username_password_token() -> None:
    assert UsernamePasswordToken in SwitchUserToken.__mro__


def test_it_carries_the_target_user_firewall_and_roles() -> None:
    token = SwitchUserToken(InMemoryUser("bob"), "api", ["ROLE_ADMIN"], _original())

    user = token.get_user()
    assert user is not None
    assert user.get_user_identifier() == "bob"
    assert token.get_firewall_name() == "api"
    assert token.get_role_names() == ("ROLE_ADMIN",)


def test_it_keeps_the_original_token() -> None:
    original = _original()
    token = SwitchUserToken(InMemoryUser("bob"), "api", ["ROLE_ADMIN"], original)

    assert token.get_original_token() is original


def test_the_uri_it_originated_from_is_optional() -> None:
    token = SwitchUserToken(InMemoryUser("bob"), "api", ["ROLE_ADMIN"], _original())

    assert token.get_originated_from_uri() is None


def test_it_carries_the_uri_it_originated_from() -> None:
    token = SwitchUserToken(InMemoryUser("bob"), "api", ["ROLE_ADMIN"], _original(), "/admin")

    assert token.get_originated_from_uri() == "/admin"


def test_an_empty_firewall_name_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="firewall_name"):
        _ = SwitchUserToken(InMemoryUser("bob"), "", ["ROLE_ADMIN"], _original())

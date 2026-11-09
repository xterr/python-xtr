"""The switch-user token carries the target user and the way back."""

from __future__ import annotations

import pytest

from tests.support.nested_tokens import NestedTokens
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


def test_a_session_keeps_the_original_through_the_codec_it_is_handed() -> None:
    original = _original()
    codec = NestedTokens()
    token = SwitchUserToken(InMemoryUser("bob"), "api", ["ROLE_ADMIN"], original, "/admin")

    state = token.to_session(codec.encode)

    assert codec.kept == [original]
    assert state == {
        "roles": ["ROLE_ADMIN"],
        "attributes": {},
        "firewall": "api",
        "original": {"place": 0},
        "originated_from_uri": "/admin",
    }


def test_it_is_rebuilt_from_a_session_with_its_original_and_where_it_was_made() -> None:
    original = _original()
    codec = NestedTokens()
    token = SwitchUserToken(InMemoryUser("bob"), "api", ["ROLE_ADMIN"], original, "/admin")
    user = InMemoryUser("bob")

    rebuilt = SwitchUserToken.from_session(token.to_session(codec.encode), user, codec.decode)

    assert rebuilt.get_user() is user
    assert rebuilt.get_firewall_name() == "api"
    assert rebuilt.get_role_names() == ("ROLE_ADMIN",)
    assert rebuilt.get_original_token() is original
    assert rebuilt.get_originated_from_uri() == "/admin"


def test_a_switch_made_at_no_uri_is_rebuilt_without_one() -> None:
    codec = NestedTokens()
    token = SwitchUserToken(InMemoryUser("bob"), "api", ["ROLE_ADMIN"], _original())

    rebuilt = SwitchUserToken.from_session(
        token.to_session(codec.encode),
        InMemoryUser("bob"),
        codec.decode,
    )

    assert rebuilt.get_originated_from_uri() is None


def test_a_session_state_whose_original_cannot_be_rebuilt_is_refused() -> None:
    state = SwitchUserToken(InMemoryUser("bob"), "api", [], _original()).to_session(
        NestedTokens().encode,
    )

    with pytest.raises(InvalidArgumentError, match="original"):
        _ = SwitchUserToken.from_session(state, InMemoryUser("bob"), NestedTokens().decode)


def test_a_session_state_whose_uri_is_no_string_is_refused() -> None:
    codec = NestedTokens()
    state = {
        **SwitchUserToken(InMemoryUser("bob"), "api", [], _original()).to_session(codec.encode),
        "originated_from_uri": 1,
    }

    with pytest.raises(InvalidArgumentError, match="originated_from_uri"):
        _ = SwitchUserToken.from_session(state, InMemoryUser("bob"), codec.decode)

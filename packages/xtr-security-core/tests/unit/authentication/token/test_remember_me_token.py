"""The remember-me token carries a remembered user and its firewall."""

from __future__ import annotations

import pytest

from tests.support.nested_tokens import nests_nothing
from xtr_security_core.authentication.token import AbstractToken, RememberMeToken
from xtr_security_core.exception import InvalidArgumentError
from xtr_security_core.user import InMemoryUser


def test_it_is_an_abstract_token() -> None:
    assert AbstractToken in RememberMeToken.__mro__


def test_it_carries_the_user_and_the_firewall() -> None:
    token = RememberMeToken(InMemoryUser("alice"), "api")

    user = token.get_user()
    assert user is not None
    assert user.get_user_identifier() == "alice"
    assert token.get_firewall_name() == "api"


def test_its_roles_are_the_users_own() -> None:
    token = RememberMeToken(InMemoryUser("alice", roles=["ROLE_USER"]), "api")

    assert token.get_role_names() == ("ROLE_USER",)


def test_an_empty_firewall_name_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="firewall_name"):
        _ = RememberMeToken(InMemoryUser("alice"), "")


def test_it_is_rebuilt_from_a_session_as_the_token_it_was() -> None:
    token = RememberMeToken(InMemoryUser("alice", roles=["ROLE_USER"]), "api")
    user = InMemoryUser("alice", roles=["ROLE_USER"])

    rebuilt = RememberMeToken.from_session(token.to_session(nests_nothing), user, nests_nothing)

    assert type(rebuilt) is RememberMeToken
    assert rebuilt.get_user() is user
    assert rebuilt.get_firewall_name() == "api"


def test_a_rebuilt_token_restores_the_roles_it_kept_not_the_users_current_ones() -> None:
    token = RememberMeToken(InMemoryUser("alice", roles=["ROLE_USER"]), "api")
    promoted = InMemoryUser("alice", roles=["ROLE_USER", "ROLE_ADMIN"])

    rebuilt = RememberMeToken.from_session(token.to_session(nests_nothing), promoted, nests_nothing)

    assert rebuilt.get_role_names() == ("ROLE_USER",)


def test_a_session_state_without_a_firewall_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="firewall"):
        _ = RememberMeToken.from_session(
            {"roles": [], "attributes": {}},
            InMemoryUser("alice"),
            nests_nothing,
        )

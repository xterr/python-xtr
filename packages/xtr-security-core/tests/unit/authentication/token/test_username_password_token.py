"""The username/password token names a user, its firewall and its roles."""

from __future__ import annotations

import pytest

from tests.support.nested_tokens import nests_nothing
from xtr_security_core.authentication.token import AbstractToken, UsernamePasswordToken
from xtr_security_core.exception import InvalidArgumentError
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


def test_an_empty_firewall_name_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="firewall_name"):
        _ = UsernamePasswordToken(InMemoryUser("alice"), "")


def test_a_session_keeps_its_firewall_beside_its_roles_and_attributes() -> None:
    token = UsernamePasswordToken(InMemoryUser("alice"), "api", ["ROLE_USER"])

    assert token.to_session(nests_nothing) == {
        "roles": ["ROLE_USER"],
        "attributes": {},
        "firewall": "api",
    }


def test_it_is_rebuilt_from_a_session_as_the_token_it_was() -> None:
    token = UsernamePasswordToken(InMemoryUser("alice"), "api", ["ROLE_USER"])
    token.set_attribute("scope", ["read"])
    user = InMemoryUser("alice")

    rebuilt = UsernamePasswordToken.from_session(
        token.to_session(nests_nothing), user, nests_nothing
    )

    assert type(rebuilt) is UsernamePasswordToken
    assert rebuilt.get_user() is user
    assert rebuilt.get_firewall_name() == "api"
    assert rebuilt.get_role_names() == ("ROLE_USER",)
    assert dict(rebuilt.get_attributes()) == {"scope": ["read"]}


@pytest.mark.parametrize("firewall", [None, "", 1])
def test_a_session_state_without_a_firewall_is_refused(firewall: object) -> None:
    state: dict[str, object] = {"roles": [], "attributes": {}, "firewall": firewall}

    with pytest.raises(InvalidArgumentError, match="firewall"):
        _ = UsernamePasswordToken.from_session(state, InMemoryUser("alice"), nests_nothing)

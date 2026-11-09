"""The abstract token carries a user, fixed roles, attributes and authentication proofs."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.nested_tokens import nests_nothing
from xtr_security_core.authentication.authentication_method import AuthenticationMethod
from xtr_security_core.authentication.token import AbstractToken
from xtr_security_core.authentication.token.token_interface import TokenInterface
from xtr_security_core.exception import InvalidArgumentError
from xtr_security_core.user import InMemoryUser

if TYPE_CHECKING:
    from collections.abc import Mapping


def test_it_inherits_the_token_interface() -> None:
    assert TokenInterface in AbstractToken.__mro__


def test_it_starts_with_no_user() -> None:
    token = AbstractToken(["ROLE_ADMIN"])

    assert token.get_user() is None
    assert token.get_role_names() == ("ROLE_ADMIN",)


def test_set_user_reports_the_user() -> None:
    user = InMemoryUser("alice", roles=("ROLE_USER",))
    token = AbstractToken(["ROLE_ADMIN"])

    token.set_user(user)

    assert token.get_user() is user
    assert token.get_user_identifier() == "alice"


def test_set_user_leaves_the_roles_untouched() -> None:
    token = AbstractToken(["ROLE_GUEST"])

    token.set_user(InMemoryUser("alice", roles=("ROLE_USER", "ROLE_ADMIN")))

    assert token.get_role_names() == ("ROLE_GUEST",)


def test_without_a_user_the_identifier_is_empty() -> None:
    assert AbstractToken().get_user_identifier() == ""


def test_attributes_round_trip() -> None:
    token = AbstractToken()
    token.set_attribute("scope", ["a", "b"])

    assert token.has_attribute("scope")
    assert token.get_attribute("scope") == ["a", "b"]
    assert dict(token.get_attributes()) == {"scope": ["a", "b"]}


def test_set_attributes_replaces_every_attribute() -> None:
    token = AbstractToken()
    token.set_attribute("a", 1)

    token.set_attributes({"b": 2})

    assert dict(token.get_attributes()) == {"b": 2}


def test_reading_a_missing_attribute_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = AbstractToken().get_attribute("missing")


def test_a_returned_snapshot_does_not_reflect_a_later_set() -> None:
    token = AbstractToken()
    token.set_attribute("a", 1)

    snapshot = token.get_attributes()
    token.set_attribute("b", 2)

    assert dict(snapshot) == {"a": 1}


def test_it_has_no_authentication_proofs_by_default() -> None:
    assert dict(AbstractToken().get_authentication_proofs()) == {}


def test_authentication_proofs_round_trip() -> None:
    token = AbstractToken()

    token.set_authentication_proofs({AuthenticationMethod.PASSWORD: 1_700_000_000})

    assert dict(token.get_authentication_proofs()) == {"pwd": 1_700_000_000}


def test_authentication_proofs_are_kept_as_an_attribute() -> None:
    token = AbstractToken()

    token.set_authentication_proofs({"otp": 1})

    assert token.get_attribute("auth_proofs") == {"otp": 1}


def test_str_names_the_class_user_and_roles() -> None:
    token = AbstractToken(["ROLE_A", "ROLE_B"])
    token.set_user(InMemoryUser("alice"))

    assert str(token) == 'AbstractToken(user="alice", roles="ROLE_A, ROLE_B")'


def test_a_session_keeps_its_roles_and_attributes_and_not_its_user() -> None:
    token = AbstractToken(["ROLE_USER"])
    token.set_user(InMemoryUser("alice"))
    token.set_attribute("scope", ["read"])

    assert token.to_session(nests_nothing) == {
        "roles": ["ROLE_USER"],
        "attributes": {"scope": ["read"]},
    }


def test_it_is_rebuilt_from_a_session_with_its_roles_attributes_and_the_user() -> None:
    token = AbstractToken(["ROLE_USER"])
    token.set_attribute("scope", ["read"])
    token.set_authentication_proofs({AuthenticationMethod.PASSWORD: 1_700_000_000})
    user = InMemoryUser("alice", roles=["ROLE_ADMIN"])

    rebuilt = AbstractToken.from_session(token.to_session(nests_nothing), user, nests_nothing)

    assert rebuilt.get_user() is user
    assert rebuilt.get_role_names() == ("ROLE_USER",)
    assert dict(rebuilt.get_attributes()) == dict(token.get_attributes())
    assert dict(rebuilt.get_authentication_proofs()) == {"pwd": 1_700_000_000}


def test_it_is_rebuilt_from_a_session_with_no_user_when_none_was_kept() -> None:
    rebuilt = AbstractToken.from_session(
        {"roles": [], "attributes": {}},
        None,
        nests_nothing,
    )

    assert rebuilt.get_user() is None


@pytest.mark.parametrize(
    "state",
    [
        {"attributes": {}},
        {"roles": ["ROLE_USER", 1], "attributes": {}},
        {"roles": [], "attributes": ["scope"]},
        {"roles": []},
    ],
)
def test_a_malformed_session_state_is_refused(state: Mapping[str, object]) -> None:
    with pytest.raises(InvalidArgumentError):
        _ = AbstractToken.from_session(state, InMemoryUser("alice"), nests_nothing)

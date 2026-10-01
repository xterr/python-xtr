"""The abstract token carries a user, fixed roles and attributes."""

from __future__ import annotations

import pytest

from xtr_security_core.authentication.token import AbstractToken
from xtr_security_core.authentication.token.token_interface import TokenInterface
from xtr_security_core.exception import InvalidArgumentError
from xtr_security_core.user import InMemoryUser


def test_it_inherits_the_token_interface() -> None:
    assert TokenInterface in AbstractToken.__mro__


def test_it_reports_user_and_roles() -> None:
    user = InMemoryUser("alice", roles=("ROLE_USER",))
    token = AbstractToken(user, ["ROLE_ADMIN"])

    assert token.get_user() is user
    assert token.get_user_identifier() == "alice"
    assert token.get_role_names() == ("ROLE_ADMIN",)


def test_its_roles_are_fixed_not_read_from_the_user() -> None:
    user = InMemoryUser("alice", roles=("ROLE_USER", "ROLE_ADMIN"))
    token = AbstractToken(user, ["ROLE_GUEST"])

    assert token.get_role_names() == ("ROLE_GUEST",)


def test_without_a_user_the_identifier_is_empty() -> None:
    assert AbstractToken().get_user_identifier() == ""


def test_attributes_round_trip() -> None:
    token = AbstractToken()
    token.set_attribute("scope", ["a", "b"])

    assert token.has_attribute("scope")
    assert token.get_attribute("scope") == ["a", "b"]
    assert dict(token.get_attributes()) == {"scope": ["a", "b"]}


def test_reading_a_missing_attribute_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = AbstractToken().get_attribute("missing")


def test_attributes_are_exposed_as_a_mapping() -> None:
    token = AbstractToken()
    token.set_attribute("a", 1)
    token.set_attribute("b", 2)

    assert dict(token.get_attributes()) == {"a": 1, "b": 2}


def test_a_returned_snapshot_does_not_reflect_a_later_set() -> None:
    token = AbstractToken()
    token.set_attribute("a", 1)

    snapshot = token.get_attributes()
    token.set_attribute("b", 2)

    assert dict(snapshot) == {"a": 1}

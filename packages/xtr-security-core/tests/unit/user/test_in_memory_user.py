"""The in-memory user carries its own identity, roles and password."""

from __future__ import annotations

import pytest
from xtr_password_hasher import PasswordAuthenticatedUserInterface

from xtr_security_core.exception import InvalidArgumentError
from xtr_security_core.user import EquatableInterface, InMemoryUser, OidcUser, UserInterface


def test_it_inherits_its_interfaces() -> None:
    for interface in (UserInterface, PasswordAuthenticatedUserInterface, EquatableInterface):
        assert interface in InMemoryUser.__mro__


def test_reports_its_fields() -> None:
    user = InMemoryUser("alice", password="hash", roles=["ROLE_USER"], enabled=True)  # noqa: S106 — a dummy hash fixture, not a secret

    assert user.get_user_identifier() == "alice"
    assert user.get_roles() == ("ROLE_USER",)
    assert user.get_password() == "hash"
    assert user.is_enabled() is True


def test_roles_are_normalised_to_a_tuple() -> None:
    user = InMemoryUser("alice", roles=["ROLE_USER", "ROLE_ADMIN"])

    assert isinstance(user.get_roles(), tuple)


def test_defaults() -> None:
    user = InMemoryUser("alice")

    assert user.get_password() is None
    assert user.get_roles() == ()
    assert user.is_enabled() is True


def test_an_empty_identifier_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = InMemoryUser("")


def test_str_is_the_identifier() -> None:
    assert str(InMemoryUser("alice")) == "alice"


def test_repr_hides_the_password() -> None:
    user = InMemoryUser("alice", password="secret-hash", roles=["ROLE_USER"])  # noqa: S106 — a dummy hash fixture, not a secret

    assert "secret-hash" not in repr(user)
    assert "password" not in repr(user)


def test_is_equal_to_the_same_fields() -> None:
    one = InMemoryUser("alice", password="h", roles=["ROLE_USER", "ROLE_ADMIN"], enabled=True)  # noqa: S106 — a dummy hash fixture, not a secret
    other = InMemoryUser("alice", password="h", roles=["ROLE_ADMIN", "ROLE_USER"], enabled=True)  # noqa: S106 — a dummy hash fixture, not a secret

    assert one.is_equal_to(other) is True


def test_is_not_equal_on_a_different_identifier() -> None:
    assert InMemoryUser("alice").is_equal_to(InMemoryUser("bob")) is False


def test_is_not_equal_on_a_different_password() -> None:
    one = InMemoryUser("alice", password="h1")  # noqa: S106 — a dummy hash fixture, not a secret
    other = InMemoryUser("alice", password="h2")  # noqa: S106 — a dummy hash fixture, not a secret

    assert one.is_equal_to(other) is False


def test_is_not_equal_on_a_different_enabled_flag() -> None:
    one = InMemoryUser("alice", enabled=True)
    other = InMemoryUser("alice", enabled=False)

    assert one.is_equal_to(other) is False


def test_is_not_equal_on_different_roles() -> None:
    one = InMemoryUser("alice", roles=["ROLE_USER"])
    other = InMemoryUser("alice", roles=["ROLE_ADMIN"])

    assert one.is_equal_to(other) is False


def test_is_not_equal_to_another_user_kind() -> None:
    assert InMemoryUser("alice").is_equal_to(OidcUser({"sub": "alice"})) is False


def test_two_users_without_a_password_are_equal() -> None:
    assert InMemoryUser("alice").is_equal_to(InMemoryUser("alice")) is True


def test_a_password_and_no_password_are_not_equal() -> None:
    one = InMemoryUser("alice", password="h")  # noqa: S106 — a dummy hash fixture, not a secret
    other = InMemoryUser("alice")

    assert one.is_equal_to(other) is False
    assert other.is_equal_to(one) is False


def test_a_non_ascii_password_compares_safely() -> None:
    one = InMemoryUser("alice", password="pässwörd")  # noqa: S106 — a dummy hash fixture, not a secret
    other = InMemoryUser("alice", password="pässwörd")  # noqa: S106 — a dummy hash fixture, not a secret

    assert one.is_equal_to(other) is True

"""The stand-in a session rebuilds for a user it kept a snapshot of."""

from __future__ import annotations

import pytest
from xtr_password_hasher import PasswordAuthenticatedUserInterface
from xtr_security_core.exception import InvalidArgumentError
from xtr_security_core.user.user_interface import UserInterface

from xtr_security_http.session import SessionUser


def test_it_is_a_user() -> None:
    assert isinstance(SessionUser("ada", ["ROLE_USER"]), UserInterface)


def test_it_answers_who_the_user_was_and_the_roles_it_held() -> None:
    user = SessionUser("ada", ["ROLE_USER", "ROLE_ADMIN"])

    assert user.get_user_identifier() == "ada"
    assert user.get_roles() == ("ROLE_USER", "ROLE_ADMIN")


def test_it_carries_no_password() -> None:
    """The comparison weighing a reload reads a password-less user as carrying none."""
    assert not isinstance(SessionUser("ada", []), PasswordAuthenticatedUserInterface)


def test_an_empty_identifier_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = SessionUser("", [])

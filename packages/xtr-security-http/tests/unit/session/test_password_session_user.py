"""The stand-in a session rebuilds for a password-carrying user, with its digest."""

from __future__ import annotations

from xtr_password_hasher import PasswordAuthenticatedUserInterface
from xtr_security_core.user.password_digest import password_digest

from xtr_security_http.session import PasswordSessionUser, SessionUser


def test_it_is_a_session_user_carrying_a_password() -> None:
    user = PasswordSessionUser("ada", ["ROLE_USER"], password_digest("hashed"))

    assert isinstance(user, SessionUser)
    assert isinstance(user, PasswordAuthenticatedUserInterface)


def test_its_password_is_the_digest_it_was_kept_with() -> None:
    user = PasswordSessionUser("ada", ["ROLE_USER"], password_digest("hashed"))

    assert user.get_password() == password_digest("hashed")
    assert user.get_user_identifier() == "ada"
    assert user.get_roles() == ("ROLE_USER",)


def test_a_user_kept_without_a_password_answers_none() -> None:
    assert PasswordSessionUser("ada", [], None).get_password() is None

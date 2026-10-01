"""The password-carrying user contract is reachable from one place."""

from __future__ import annotations

from xtr_password_hasher import PasswordAuthenticatedUserInterface

from xtr_security_core import user


def test_password_authenticated_user_interface_is_re_exported() -> None:
    assert user.PasswordAuthenticatedUserInterface is PasswordAuthenticatedUserInterface

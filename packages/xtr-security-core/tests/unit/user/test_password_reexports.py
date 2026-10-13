"""The password-carrying user contracts are reachable from one place."""

from __future__ import annotations

from xtr_password_hasher import (
    LegacyPasswordAuthenticatedUserInterface,
    PasswordAuthenticatedUserInterface,
)

from xtr_security_core import user
from xtr_security_core.user import password_authenticated_user_interface


def test_password_authenticated_user_interface_is_re_exported() -> None:
    assert user.PasswordAuthenticatedUserInterface is PasswordAuthenticatedUserInterface


def test_it_is_re_exported_from_its_own_module_too() -> None:
    assert (
        password_authenticated_user_interface.PasswordAuthenticatedUserInterface
        is PasswordAuthenticatedUserInterface
    )


def test_legacy_password_authenticated_user_interface_is_re_exported() -> None:
    assert user.LegacyPasswordAuthenticatedUserInterface is LegacyPasswordAuthenticatedUserInterface

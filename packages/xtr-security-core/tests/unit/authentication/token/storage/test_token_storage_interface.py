"""The token-storage interface is a runtime-checkable structural protocol."""

from __future__ import annotations

from xtr_security_core.authentication.token.storage import TokenStorage, TokenStorageInterface


def test_the_storage_satisfies_the_interface() -> None:
    assert isinstance(TokenStorage(), TokenStorageInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), TokenStorageInterface)

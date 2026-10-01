from __future__ import annotations

from xtr_password_hasher import PasswordHasherAwareInterface


class _Aware:
    def get_password_hasher_name(self) -> str | None:
        return "custom"


class _NotAware:
    pass


def test_a_user_that_names_a_hasher_satisfies_it() -> None:
    assert isinstance(_Aware(), PasswordHasherAwareInterface)


def test_a_user_without_the_method_does_not() -> None:
    assert not isinstance(_NotAware(), PasswordHasherAwareInterface)

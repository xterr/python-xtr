"""The account-status base error carries the user it is about."""

from __future__ import annotations

from xtr_security_core.exception import AccountStatusError, AuthenticationError
from xtr_security_core.user import InMemoryUser


def test_it_is_an_authentication_error() -> None:
    assert issubclass(AccountStatusError, AuthenticationError)


def test_it_carries_the_user() -> None:
    user = InMemoryUser("alice")
    error = AccountStatusError(user)

    assert error.user is user

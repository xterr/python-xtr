"""The account-status base error carries the user it is about."""

from __future__ import annotations

from xtr_security_core.exception import AccountStatusError, AuthenticationError, LockedError
from xtr_security_core.user import InMemoryUser


def test_it_is_an_authentication_error() -> None:
    assert issubclass(AccountStatusError, AuthenticationError)


def test_it_carries_the_user() -> None:
    user = InMemoryUser("alice")
    error = AccountStatusError(user)

    assert error.user is user


def test_a_session_keeps_none_of_the_user() -> None:
    error = AccountStatusError(InMemoryUser("alice"), "alice is locked out")

    assert error.to_session() == {
        "message_key": AccountStatusError.MESSAGE_KEY,
        "message_data": {},
    }


def test_it_is_rebuilt_from_a_session_naming_no_user() -> None:
    rebuilt = LockedError.from_session(LockedError.MESSAGE_KEY, {})

    assert type(rebuilt) is LockedError
    assert rebuilt.user is None
    assert rebuilt.get_message_key() == LockedError.MESSAGE_KEY

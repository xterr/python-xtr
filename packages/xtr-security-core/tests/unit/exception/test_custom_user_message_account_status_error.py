"""The custom-message account-status error shows its own key."""

from __future__ import annotations

from xtr_security_core.exception import AccountStatusError, CustomUserMessageAccountStatusError


def test_it_is_an_account_status_error() -> None:
    assert issubclass(CustomUserMessageAccountStatusError, AccountStatusError)


def test_it_shows_its_key() -> None:
    error = CustomUserMessageAccountStatusError("Subscription lapsed.")

    assert error.get_message_key() == "Subscription lapsed."

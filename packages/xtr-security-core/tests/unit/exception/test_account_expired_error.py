"""The account-expired error names its own status."""

from __future__ import annotations

from xtr_security_core.exception import AccountExpiredError, AccountStatusError


def test_it_is_an_account_status_error() -> None:
    assert issubclass(AccountExpiredError, AccountStatusError)


def test_its_public_key() -> None:
    assert AccountExpiredError().get_message_key() == "Account has expired."

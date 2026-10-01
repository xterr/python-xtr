"""The locked-account error names its own status."""

from __future__ import annotations

from xtr_security_core.exception import AccountStatusError, LockedError


def test_it_is_an_account_status_error() -> None:
    assert issubclass(LockedError, AccountStatusError)


def test_its_public_key() -> None:
    assert LockedError().get_message_key() == "Account is locked."

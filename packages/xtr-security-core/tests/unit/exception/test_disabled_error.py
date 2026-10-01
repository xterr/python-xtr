"""The disabled-account error names its own status."""

from __future__ import annotations

from xtr_security_core.exception import AccountStatusError, DisabledError


def test_it_is_an_account_status_error() -> None:
    assert issubclass(DisabledError, AccountStatusError)


def test_its_public_key() -> None:
    assert DisabledError().get_message_key() == "Account is disabled."

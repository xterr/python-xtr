"""The credentials-expired error names its own status."""

from __future__ import annotations

from xtr_security_core.exception import AccountStatusError, CredentialsExpiredError


def test_it_is_an_account_status_error() -> None:
    assert issubclass(CredentialsExpiredError, AccountStatusError)


def test_its_public_key() -> None:
    assert CredentialsExpiredError().get_message_key() == "Credentials have expired."

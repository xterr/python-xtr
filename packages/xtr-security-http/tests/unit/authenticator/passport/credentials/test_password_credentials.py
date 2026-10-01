"""Password credentials are consumed once and drop their plaintext."""

from __future__ import annotations

import pytest
from xtr_security_core.exception import InvalidArgumentError

from xtr_security_http.authenticator.passport.credentials.password_credentials import (
    PasswordCredentials,
)


def test_the_plaintext_is_readable_until_resolved() -> None:
    credentials = PasswordCredentials("secret")

    assert credentials.get_password() == "secret"
    assert credentials.is_resolved() is False


def test_resolving_drops_the_plaintext() -> None:
    credentials = PasswordCredentials("secret")

    credentials.mark_resolved()

    assert credentials.is_resolved() is True
    with pytest.raises(InvalidArgumentError):
        _ = credentials.get_password()

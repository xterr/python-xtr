"""The credentials interface is a runtime-checkable structural protocol."""

from __future__ import annotations

from xtr_security_http.authenticator.passport.credentials.credentials_interface import (
    CredentialsInterface,
)
from xtr_security_http.authenticator.passport.credentials.password_credentials import (
    PasswordCredentials,
)


def test_credentials_satisfy_the_interface() -> None:
    assert isinstance(PasswordCredentials("x"), CredentialsInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), CredentialsInterface)

"""The invalid-grant error is the one a caller has to tell apart."""

from __future__ import annotations

from xtr_security_core.exception import AuthenticationError

from xtr_security_http.exception import OidcInvalidGrantError


def test_it_is_an_authentication_error() -> None:
    assert issubclass(OidcInvalidGrantError, AuthenticationError)


def test_its_public_message_names_the_rejected_grant() -> None:
    assert OidcInvalidGrantError.MESSAGE_KEY == "The OIDC provider rejected the grant."


def test_an_instance_carries_the_message_key() -> None:
    error = OidcInvalidGrantError("The provider said no.")

    assert error.message_key == "The OIDC provider rejected the grant."

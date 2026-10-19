"""The session-ended error is the reason a back-channel logout deauthenticates by."""

from __future__ import annotations

from xtr_security_core.exception import AuthenticationError

from xtr_security_http.exception import OidcSessionEndedError


def test_it_is_an_authentication_error() -> None:
    assert issubclass(OidcSessionEndedError, AuthenticationError)


def test_its_public_message_names_the_ended_session() -> None:
    assert (
        OidcSessionEndedError.MESSAGE_KEY
        == "The OIDC provider ended the session this login belongs to."
    )


def test_an_instance_carries_the_message_key() -> None:
    error = OidcSessionEndedError("The provider said so.")

    assert error.message_key == "The OIDC provider ended the session this login belongs to."

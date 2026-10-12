"""A client acting for itself stands where a resource owner would."""

from __future__ import annotations

from xtr_security_core.user.user_interface import UserInterface

from xtr_security_oauth2_server.security.user.client_credentials_user import ClientCredentialsUser

CLIENT_ID = "a-client"


def test_the_identifier_is_the_client_the_token_was_issued_to() -> None:
    assert ClientCredentialsUser(CLIENT_ID).get_user_identifier() == CLIENT_ID


def test_it_holds_no_role_of_its_own() -> None:
    # Whatever such a caller may do comes from the token's scopes, which the
    # token turns into roles itself; a role here would be granted to every
    # client-credentials caller regardless of what it asked for.
    assert ClientCredentialsUser(CLIENT_ID).get_roles() == ()


def test_it_is_a_user_the_family_can_put_on_a_token() -> None:
    assert isinstance(ClientCredentialsUser(CLIENT_ID), UserInterface)


def test_the_reading_names_the_client_it_stands_for() -> None:
    assert CLIENT_ID in repr(ClientCredentialsUser(CLIENT_ID))

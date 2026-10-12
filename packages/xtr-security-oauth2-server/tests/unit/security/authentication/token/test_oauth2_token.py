"""A read access token becomes a caller whose scopes are roles."""

from __future__ import annotations

from xtr_security_core.user.in_memory_user import InMemoryUser

from xtr_security_oauth2_server.security.authentication.token.oauth2_token import (
    ACCESS_TOKEN_ID_ATTRIBUTE,
    CLIENT_ID_ATTRIBUTE,
    SCOPE_ATTRIBUTE,
    SCOPES_ATTRIBUTE,
    OAuth2Token,
)

FIREWALL = "api"
ACCESS_TOKEN_ID = "access-token-id"
CLIENT_ID = "a-client"
PREFIX = "ROLE_OAUTH2_"


def _token(
    scopes: tuple[str, ...] = ("orders:read",),
    roles: list[str] | None = None,
) -> OAuth2Token:
    """Return a token for a user holding ``roles``, carrying ``scopes``."""
    user = InMemoryUser("ada", roles=roles if roles is not None else [])

    return OAuth2Token(user, FIREWALL, ACCESS_TOKEN_ID, CLIENT_ID, scopes, PREFIX)


def test_a_scope_becomes_a_prefixed_upper_cased_role() -> None:
    assert "ROLE_OAUTH2_ORDERS:READ" in _token().get_role_names()


def test_the_resource_owners_own_roles_are_kept_beside_the_scopes() -> None:
    # A token grants on top of who somebody is, not instead of it.
    granted = _token(roles=["ROLE_USER"]).get_role_names()

    assert "ROLE_OAUTH2_ORDERS:READ" in granted
    assert "ROLE_USER" in granted


def test_a_role_granted_by_both_the_scope_and_the_user_appears_once() -> None:
    granted = _token(scopes=("orders:read",), roles=["ROLE_OAUTH2_ORDERS:READ"]).get_role_names()

    assert list(granted).count("ROLE_OAUTH2_ORDERS:READ") == 1


def test_a_token_carrying_no_scope_grants_only_what_the_user_is() -> None:
    assert list(_token(scopes=(), roles=["ROLE_USER"]).get_role_names()) == ["ROLE_USER"]


def test_the_scopes_are_kept_exactly_as_they_were_issued() -> None:
    # A role is lossy — prefixed and upper cased — so the scopes are kept too.
    assert _token(scopes=("orders:read", "orders:write")).get_scopes() == (
        "orders:read",
        "orders:write",
    )


def test_the_scope_voter_reads_the_scopes_off_its_own_attribute() -> None:
    assert _token().get_attribute(SCOPE_ATTRIBUTE) == ("orders:read",)


def test_the_reference_attribute_names_carry_the_same_data() -> None:
    token = _token()

    assert token.get_attribute(SCOPES_ATTRIBUTE) == ("orders:read",)
    assert token.get_attribute(ACCESS_TOKEN_ID_ATTRIBUTE) == ACCESS_TOKEN_ID
    assert token.get_attribute(CLIENT_ID_ATTRIBUTE) == CLIENT_ID


def test_the_credentials_are_the_identifier_of_the_token_presented() -> None:
    assert _token().get_credentials() == ACCESS_TOKEN_ID


def test_the_client_the_token_was_issued_to_is_reported() -> None:
    assert _token().get_oauth_client_id() == CLIENT_ID


def test_the_firewall_that_read_the_token_is_kept() -> None:
    assert _token().get_firewall_name() == FIREWALL


def test_the_resource_owner_is_the_user_the_token_named() -> None:
    assert _token().get_user_identifier() == "ada"


def test_the_reading_names_the_caller_and_the_client_but_never_the_token() -> None:
    # The identifier is what withdraws the token, so it stays out of a log line.
    shown = repr(_token())

    assert "ada" in shown
    assert CLIENT_ID in shown
    assert ACCESS_TOKEN_ID not in shown

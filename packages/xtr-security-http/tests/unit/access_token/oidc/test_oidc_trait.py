"""The OIDC trait builds the user from claims and weighs discovered endpoints."""

from __future__ import annotations

import pytest
from xtr_security_core.user.oidc_user import OidcUser

from xtr_security_http.access_token.oidc import OidcTrait
from xtr_security_http.exception import InvalidAccessTokenError


def test_create_user_builds_the_oidc_user_from_the_claims() -> None:
    user = OidcTrait().create_user(
        {
            "sub": "alice",
            "email": "alice@example.com",
            "roles": ["ROLE_ADMIN"],
            "department": "sales",
        },
    )

    assert isinstance(user, OidcUser)
    assert user.get_user_identifier() == "alice"
    assert user.get_email() == "alice@example.com"
    assert user.get_roles() == ("ROLE_ADMIN",)
    assert user.get_additional_claims() == {"department": "sales"}


def test_create_user_names_the_user_by_the_user_identifier_claim() -> None:
    user = OidcTrait().create_user({"sub": "alice", "user_identifier": "alice@local"})

    assert user.get_user_identifier() == "alice@local"
    assert user.get_sub() == "alice"


@pytest.mark.parametrize("endpoint", [None, "", 42, ["https://issuer.example/userinfo"]])
def test_an_endpoint_that_is_not_a_non_empty_string_is_refused(endpoint: object) -> None:
    with pytest.raises(InvalidAccessTokenError) as raised:
        _ = OidcTrait.check_discovered_endpoint(
            endpoint, "userinfo_endpoint", "https://issuer.example"
        )

    assert (
        str(raised.value) == 'The "userinfo_endpoint" is missing from the OIDC discovery document.'
    )


def test_an_http_endpoint_of_an_https_discovery_url_is_refused() -> None:
    with pytest.raises(InvalidAccessTokenError) as raised:
        _ = OidcTrait.check_discovered_endpoint(
            "http://issuer.example/userinfo",
            "userinfo_endpoint",
            "https://issuer.example",
        )

    assert str(raised.value) == (
        'The "userinfo_endpoint" found in the OIDC discovery document must use the '
        '"https" scheme, "http" given.'
    )


def test_an_http_endpoint_of_an_http_discovery_url_is_allowed() -> None:
    endpoint = OidcTrait.check_discovered_endpoint(
        "http://issuer.example/userinfo",
        "userinfo_endpoint",
        "http://issuer.example",
    )

    assert endpoint == "http://issuer.example/userinfo"


def test_an_https_endpoint_of_an_https_discovery_url_is_allowed() -> None:
    endpoint = OidcTrait.check_discovered_endpoint(
        "https://issuer.example/userinfo",
        "userinfo_endpoint",
        "https://issuer.example",
    )

    assert endpoint == "https://issuer.example/userinfo"


def test_an_endpoint_naming_no_scheme_is_allowed() -> None:
    endpoint = OidcTrait.check_discovered_endpoint(
        "issuer.example/userinfo",
        "userinfo_endpoint",
        "https://issuer.example",
    )

    assert endpoint == "issuer.example/userinfo"


def test_an_http_endpoint_is_allowed_when_the_discovery_url_is_unknown() -> None:
    endpoint = OidcTrait.check_discovered_endpoint(
        "http://issuer.example/userinfo",
        "userinfo_endpoint",
        None,
    )

    assert endpoint == "http://issuer.example/userinfo"

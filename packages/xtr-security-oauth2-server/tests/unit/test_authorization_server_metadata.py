"""The document a client reads to find out what this server can do."""

from __future__ import annotations

from typing import Final

import pytest

from xtr_security_oauth2_server.authorization_server_metadata import AuthorizationServerMetadata
from xtr_security_oauth2_server.exception.invalid_argument_error import InvalidArgumentError

_ISSUER: Final[str] = "https://authorization.example.com"
_TOKEN: Final[str] = "https://authorization.example.com/token"
_AUTHORIZE: Final[str] = "https://authorization.example.com/authorize"


def test_the_document_names_the_issuer_it_was_built_for() -> None:
    document = AuthorizationServerMetadata(_ISSUER).to_dict()

    assert document["issuer"] == _ISSUER


def test_only_the_endpoints_it_was_given_are_named() -> None:
    document = AuthorizationServerMetadata(_ISSUER, {"token_endpoint": _TOKEN}).to_dict()

    assert document["token_endpoint"] == _TOKEN
    assert "authorization_endpoint" not in document
    assert "device_authorization_endpoint" not in document


def test_the_scopes_it_knows_are_named_when_there_are_any() -> None:
    document = AuthorizationServerMetadata(_ISSUER, {}, (), ("read", "write")).to_dict()

    assert document["scopes_supported"] == ["read", "write"]


def test_no_scopes_means_the_field_is_left_out() -> None:
    assert "scopes_supported" not in AuthorizationServerMetadata(_ISSUER).to_dict()


def test_the_grants_it_runs_are_named() -> None:
    document = AuthorizationServerMetadata(_ISSUER, {}, ("client_credentials",)).to_dict()

    assert document["grant_types_supported"] == ["client_credentials"]


def test_no_grants_means_the_field_is_left_out() -> None:
    assert "grant_types_supported" not in AuthorizationServerMetadata(_ISSUER).to_dict()


def test_the_response_types_follow_from_the_grants_that_redirect() -> None:
    document = AuthorizationServerMetadata(
        _ISSUER,
        {},
        ("authorization_code", "implicit", "client_credentials"),
    ).to_dict()

    assert document["response_types_supported"] == ["code", "token"]


def test_a_server_that_redirects_nobody_supports_no_response_type() -> None:
    document = AuthorizationServerMetadata(_ISSUER, {}, ("client_credentials",)).to_dict()

    assert document["response_types_supported"] == []


def test_the_token_endpoint_names_how_a_client_may_authenticate_to_it() -> None:
    document = AuthorizationServerMetadata(_ISSUER, {"token_endpoint": _TOKEN}).to_dict()

    assert document["token_endpoint_auth_methods_supported"] == [
        "client_secret_basic",
        "client_secret_post",
        "none",
    ]


def test_without_a_token_endpoint_no_authentication_methods_are_named() -> None:
    document = AuthorizationServerMetadata(_ISSUER, {"authorization_endpoint": _AUTHORIZE})

    assert "token_endpoint_auth_methods_supported" not in document.to_dict()


def test_the_revocation_endpoint_names_its_own_authentication_methods() -> None:
    endpoints = {"revocation_endpoint": "https://authorization.example.com/revoke"}

    document = AuthorizationServerMetadata(_ISSUER, endpoints).to_dict()

    assert document["revocation_endpoint_auth_methods_supported"] == [
        "client_secret_basic",
        "client_secret_post",
        "none",
    ]


def test_without_a_revocation_endpoint_it_names_none() -> None:
    document = AuthorizationServerMetadata(_ISSUER, {"token_endpoint": _TOKEN}).to_dict()

    assert "revocation_endpoint_auth_methods_supported" not in document


def test_the_introspection_endpoint_names_its_own_authentication_methods() -> None:
    endpoints = {"introspection_endpoint": "https://authorization.example.com/introspect"}

    document = AuthorizationServerMetadata(_ISSUER, endpoints).to_dict()

    assert document["introspection_endpoint_auth_methods_supported"] == [
        "client_secret_basic",
        "client_secret_post",
        "none",
    ]


def test_the_proof_key_methods_it_accepts_are_named_when_there_are_any() -> None:
    document = AuthorizationServerMetadata(_ISSUER, {}, (), (), ("S256", "plain")).to_dict()

    assert document["code_challenge_methods_supported"] == ["S256", "plain"]


def test_no_proof_key_methods_means_the_field_is_left_out() -> None:
    assert "code_challenge_methods_supported" not in AuthorizationServerMetadata(_ISSUER).to_dict()


def test_a_field_an_extension_contributes_is_carried() -> None:
    document = AuthorizationServerMetadata(
        _ISSUER,
        {},
        (),
        (),
        (),
        {"userinfo_endpoint": "https://authorization.example.com/userinfo"},
    ).to_dict()

    assert document["userinfo_endpoint"] == "https://authorization.example.com/userinfo"


def test_a_contributed_field_cannot_take_over_one_the_server_decides() -> None:
    document = AuthorizationServerMetadata(
        _ISSUER,
        {"token_endpoint": _TOKEN},
        (),
        (),
        (),
        {"issuer": "https://evil.example.com", "token_endpoint": "https://evil.example.com/t"},
    ).to_dict()

    assert document["issuer"] == _ISSUER
    assert document["token_endpoint"] == _TOKEN


def test_an_endpoint_this_document_has_no_field_for_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="userinfo_endpoint"):
        _ = AuthorizationServerMetadata(_ISSUER, {"userinfo_endpoint": "https://e.example.com"})


def test_an_issuer_carrying_a_path_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="origin"):
        _ = AuthorizationServerMetadata("https://authorization.example.com/tenant-1")


def test_an_issuer_carrying_a_query_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="origin"):
        _ = AuthorizationServerMetadata("https://authorization.example.com?tenant=1")


def test_an_issuer_that_names_no_scheme_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="origin"):
        _ = AuthorizationServerMetadata("authorization.example.com")


def test_an_issuer_that_names_no_host_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="origin"):
        _ = AuthorizationServerMetadata("https://")


def test_an_issuer_with_a_port_is_an_origin() -> None:
    document = AuthorizationServerMetadata("http://localhost:8000").to_dict()

    assert document["issuer"] == "http://localhost:8000"


def test_its_reading_names_the_issuer_and_the_endpoints_it_hosts() -> None:
    shown = repr(AuthorizationServerMetadata(_ISSUER, {"token_endpoint": _TOKEN}))

    assert _ISSUER in shown
    assert "token_endpoint" in shown

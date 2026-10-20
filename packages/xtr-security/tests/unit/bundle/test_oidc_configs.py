"""The OIDC login configuration validates its fields."""

from __future__ import annotations

import pytest

from xtr_security.bundle import OidcLoginConfig, OidcTokenGeneratorConfig
from xtr_security.exception import InvalidConfigurationError


def test_a_login_needs_an_issuer() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = OidcLoginConfig(issuer="", client_id="shop")


def test_a_login_needs_its_client_id() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = OidcLoginConfig(issuer="https://issuer.example", client_id="")


def test_a_login_refuses_an_unknown_endpoint_authentication_method() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = OidcLoginConfig(
            issuer="https://issuer.example",
            client_id="shop",
            token_endpoint_auth_method="shared_secret",  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        )


def test_a_secret_bearing_method_needs_the_client_secret() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = OidcLoginConfig(
            issuer="https://issuer.example",
            client_id="shop",
            token_endpoint_auth_method="client_secret_basic",
            client_secret=None,
        )


def test_a_public_method_refuses_a_client_secret() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = OidcLoginConfig(
            issuer="https://issuer.example",
            client_id="shop",
            token_endpoint_auth_method="none",
            client_secret="secret",
        )


def test_a_public_client_builds_without_a_secret() -> None:
    config = OidcLoginConfig(
        issuer="https://issuer.example",
        client_id="shop",
        token_endpoint_auth_method="none",
    )

    assert config.client_secret is None


def test_private_key_jwt_needs_its_signing_key() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = OidcLoginConfig(
            issuer="https://issuer.example",
            client_id="shop",
            client_secret="secret",
            token_endpoint_auth_method="private_key_jwt",
            client_authentication_keyset=None,
        )


def test_a_login_refuses_an_unknown_pkce_method() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = OidcLoginConfig(
            issuer="https://issuer.example",
            client_id="shop",
            client_secret="secret",
            pkce_method="S512",
        )


def test_a_login_refuses_an_unknown_user_data_source() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = OidcLoginConfig(
            issuer="https://issuer.example",
            client_id="shop",
            client_secret="secret",
            user_data_source="elsewhere",
        )


def test_a_login_keeps_its_fields() -> None:
    generator = OidcTokenGeneratorConfig(
        algorithms=("RS256",),
        keyset='{"keys": []}',
        audience="shop-api",
        issuers=("https://issuer.example",),
    )
    config = OidcLoginConfig(
        issuer="https://issuer.example",
        client_id="shop",
        client_secret="secret",
        token_endpoint_auth_method="client_secret_post",
        scope="openid profile",
        check_path="/login/oidc/check",
        pkce_enabled=False,
        user_data_source="id_token",
        user_identifier_claim="preferred_username",
        max_age=3600,
        authorization_params={"audience": "shop-api"},
        signature_verifier_algorithms=("RS256", "ES256"),
        client_authentication_keyset='{"keys": []}',
        certificate_options={"local_cert": "cert.pem"},
        token_generator=generator,
    )

    assert config.issuer == "https://issuer.example"
    assert config.client_id == "shop"
    assert config.client_secret == "secret"
    assert config.token_endpoint_auth_method == "client_secret_post"
    assert config.scope == "openid profile"
    assert config.check_path == "/login/oidc/check"
    assert config.pkce_enabled is False
    assert config.user_data_source == "id_token"
    assert config.user_identifier_claim == "preferred_username"
    assert config.max_age == 3600
    assert dict(config.authorization_params) == {"audience": "shop-api"}
    assert tuple(config.signature_verifier_algorithms or ()) == ("RS256", "ES256")
    assert config.client_authentication_keyset == '{"keys": []}'
    assert config.certificate_options == {"local_cert": "cert.pem"}
    assert config.token_generator is generator


def test_a_login_defaults_to_the_documented_choices() -> None:
    config = OidcLoginConfig(
        issuer="https://issuer.example",
        client_id="shop",
        client_secret="secret",
    )

    assert config.token_endpoint_auth_method == "client_secret_basic"
    assert config.scope == "openid"
    assert config.check_path == "/oidc/callback"
    assert config.pkce_enabled is True
    assert config.pkce_method == "S256"
    assert config.user_data_source == "userinfo"
    assert config.user_identifier_claim == "sub"
    assert config.max_age is None
    assert dict(config.authorization_params) == {}
    assert config.signature_verifier_algorithms is None
    assert config.client_authentication_keyset is None
    assert config.certificate_options is None
    assert config.token_generator is None


def test_a_generator_needs_its_algorithms() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = OidcTokenGeneratorConfig(
            algorithms=(),
            keyset='{"keys": []}',
            audience="shop-api",
            issuers=("https://issuer.example",),
        )


def test_a_generator_needs_its_signing_keys() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = OidcTokenGeneratorConfig(
            algorithms=("RS256",),
            keyset="",
            audience="shop-api",
            issuers=("https://issuer.example",),
        )


def test_a_generator_needs_an_audience() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = OidcTokenGeneratorConfig(
            algorithms=("RS256",),
            keyset='{"keys": []}',
            audience="",
            issuers=("https://issuer.example",),
        )


def test_a_generator_needs_its_issuers() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = OidcTokenGeneratorConfig(
            algorithms=("RS256",),
            keyset='{"keys": []}',
            audience="shop-api",
            issuers=(),
        )


def test_a_generator_keeps_its_fields() -> None:
    config = OidcTokenGeneratorConfig(
        algorithms=("RS256", "ES256"),
        keyset='{"keys": []}',
        audience=("shop-api", "admin-api"),
        issuers=("https://issuer.example",),
        claim="preferred_username",
    )

    assert tuple(config.algorithms) == ("RS256", "ES256")
    assert config.keyset == '{"keys": []}'
    assert config.audience == ("shop-api", "admin-api")
    assert tuple(config.issuers) == ("https://issuer.example",)
    assert config.claim == "preferred_username"

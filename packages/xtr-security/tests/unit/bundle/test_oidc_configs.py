"""The OIDC login configuration validates its fields."""

from __future__ import annotations

import pytest
from xtr_dependency_injection import env

from tests.support.environment import resolved
from xtr_security.bundle import (
    OidcBackChannelLogoutConfig,
    OidcEndSessionConfig,
    OidcLoginConfig,
    OidcTokenGeneratorConfig,
)
from xtr_security.exception import InvalidConfigurationError


def test_a_login_needs_an_issuer() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = OidcLoginConfig(issuer="", client_id="shop")


def test_a_login_needs_its_client_id() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = OidcLoginConfig(issuer="https://issuer.example", client_id="")


def test_a_login_refuses_a_redirect_uri_that_is_no_absolute_url() -> None:
    with pytest.raises(InvalidConfigurationError, match="absolute URL"):
        _ = OidcLoginConfig(
            issuer="https://issuer.example",
            client_id="shop",
            client_secret="secret",
            redirect_uri="/oidc/callback",
        )


def test_a_login_refuses_a_redirect_uri_off_its_check_path() -> None:
    with pytest.raises(InvalidConfigurationError, match="check_path"):
        _ = OidcLoginConfig(
            issuer="https://issuer.example",
            client_id="shop",
            client_secret="secret",
            redirect_uri="https://shop.example/elsewhere",
        )


def test_a_redirect_uri_on_the_check_path_is_kept() -> None:
    config = OidcLoginConfig(
        issuer="https://issuer.example",
        client_id="shop",
        client_secret="secret",
        check_path="/callback",
        redirect_uri="https://shop.example/callback",
    )

    assert config.redirect_uri == "https://shop.example/callback"


def test_a_redirect_uri_may_be_read_from_the_environment() -> None:
    config = OidcLoginConfig(
        issuer="https://issuer.example",
        client_id="shop",
        client_secret="secret",
        redirect_uri=env("OIDC_REDIRECT_URI"),
    )

    built = resolved(config, {"OIDC_REDIRECT_URI": "https://shop.example/oidc/callback"})

    assert built.redirect_uri == "https://shop.example/oidc/callback"


def test_a_login_refuses_a_failure_path_that_is_no_absolute_path() -> None:
    with pytest.raises(InvalidConfigurationError, match="not an absolute path"):
        _ = OidcLoginConfig(
            issuer="https://issuer.example",
            client_id="shop",
            client_secret="secret",
            failure_path="sign-in-failed",
        )


def test_a_failure_path_may_be_read_from_the_environment() -> None:
    config = OidcLoginConfig(
        issuer="https://issuer.example",
        client_id="shop",
        client_secret="secret",
        failure_path=env("OIDC_FAILURE_PATH"),
    )

    built = resolved(config, {"OIDC_FAILURE_PATH": "/sign-in-failed"})

    assert built.failure_path == "/sign-in-failed"


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
        failure_path="/login/oidc/failed",
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
    assert config.failure_path == "/login/oidc/failed"
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
    assert config.failure_path is None
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
    assert config.backchannel_logout is None
    assert config.end_session is None


def test_a_backchannel_logout_refuses_a_route_name() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = OidcBackChannelLogoutConfig(route="app_logout")


def test_a_backchannel_logout_refuses_a_non_positive_lifetime() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = OidcBackChannelLogoutConfig(lifetime=0)


def test_a_backchannel_logout_keeps_its_fields() -> None:
    backchannel = OidcBackChannelLogoutConfig(route="/logout/provider", lifetime=7200)

    assert backchannel.enable is True
    assert backchannel.route == "/logout/provider"
    assert backchannel.lifetime == 7200


def test_an_end_session_refuses_a_route_name() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = OidcEndSessionConfig(post_logout_redirect_path="home")


def test_an_end_session_keeps_its_fields() -> None:
    end_session = OidcEndSessionConfig(post_logout_redirect_path="/bye")

    assert end_session.enable is True
    assert end_session.post_logout_redirect_path == "/bye"


def test_a_login_carries_its_backchannel_and_end_session() -> None:
    backchannel = OidcBackChannelLogoutConfig()
    end_session = OidcEndSessionConfig()
    config = OidcLoginConfig(
        issuer="https://issuer.example",
        client_id="shop",
        client_secret="secret",
        backchannel_logout=backchannel,
        end_session=end_session,
    )

    assert config.backchannel_logout is backchannel
    assert config.end_session is end_session


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


def test_a_logins_issuer_and_client_may_be_read_from_the_environment() -> None:
    config = OidcLoginConfig(
        issuer=env("OIDC_ISSUER"), client_id=env("OIDC_CLIENT_ID"), client_secret="secret"
    )

    built = resolved(config, {"OIDC_ISSUER": "https://issuer.example", "OIDC_CLIENT_ID": "shop"})

    assert (built.issuer, built.client_id) == ("https://issuer.example", "shop")


def test_a_generators_keys_and_audience_may_be_read_from_the_environment() -> None:
    config = OidcTokenGeneratorConfig(
        algorithms=("RS256",),
        keyset=env("OIDC_KEYSET"),
        audience=env("OIDC_AUDIENCE"),
        issuers=("https://issuer.example",),
    )

    built = resolved(config, {"OIDC_KEYSET": '{"keys": []}', "OIDC_AUDIENCE": "shop-api"})

    assert (built.keyset, built.audience) == ('{"keys": []}', "shop-api")


def test_a_back_channel_route_may_be_read_from_the_environment() -> None:
    config = OidcBackChannelLogoutConfig(route=env("BACKCHANNEL_ROUTE"))

    assert resolved(config, {"BACKCHANNEL_ROUTE": "/bc"}).route == "/bc"


def test_a_back_channel_route_the_environment_makes_relative_is_refused() -> None:
    config = OidcBackChannelLogoutConfig(route=env("BACKCHANNEL_ROUTE"))

    with pytest.raises(InvalidConfigurationError, match="not an absolute path"):
        _ = resolved(config, {"BACKCHANNEL_ROUTE": "bc"})


def test_an_end_session_redirect_may_be_read_from_the_environment() -> None:
    config = OidcEndSessionConfig(post_logout_redirect_path=env("BYE_PATH"))

    assert resolved(config, {"BYE_PATH": "/bye"}).post_logout_redirect_path == "/bye"


def test_an_end_session_redirect_the_environment_makes_relative_is_refused() -> None:
    config = OidcEndSessionConfig(post_logout_redirect_path=env("BYE_PATH"))

    with pytest.raises(InvalidConfigurationError, match="not an absolute path"):
        _ = resolved(config, {"BYE_PATH": "bye"})

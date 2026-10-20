"""The access-token authenticator configuration validates its extractors."""

from __future__ import annotations

import pytest

from xtr_security.bundle import AccessTokenConfig, HttpBasicConfig, ServiceTokenHandlerConfig
from xtr_security.exception import InvalidConfigurationError


class _Handler:
    """A stand-in handler class."""


def test_it_defaults_to_the_header_extractor() -> None:
    config = AccessTokenConfig(token_handler=ServiceTokenHandlerConfig(_Handler))

    assert config.token_extractors == ("header",)


def test_it_accepts_the_known_extractors() -> None:
    config = AccessTokenConfig(
        token_handler=ServiceTokenHandlerConfig(_Handler),
        token_extractors=("header", "query", "body"),
    )

    assert config.token_extractors == ("header", "query", "body")


def test_it_defaults_to_no_resource_metadata_and_no_sender_constraint() -> None:
    config = AccessTokenConfig(token_handler=ServiceTokenHandlerConfig(_Handler))

    assert config.resource_metadata_uri is None
    assert config.sender_constraint is None


def test_it_keeps_the_resource_metadata_uri_and_the_sender_constraint_name() -> None:
    config = AccessTokenConfig(
        token_handler=ServiceTokenHandlerConfig(_Handler),
        resource_metadata_uri="/.well-known/oauth-protected-resource",
        sender_constraint="api.constraint",
    )

    assert config.resource_metadata_uri == "/.well-known/oauth-protected-resource"
    assert config.sender_constraint == "api.constraint"


def test_an_http_basic_authenticator_defaults_to_the_secured_realm() -> None:
    config = HttpBasicConfig()

    assert config.realm == "Secured"


def test_an_http_basic_authenticator_keeps_its_realm() -> None:
    config = HttpBasicConfig(realm="api")

    assert config.realm == "api"


def test_an_http_basic_authenticator_needs_a_realm() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = HttpBasicConfig(realm="")


def test_it_refuses_no_extractor() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = AccessTokenConfig(
            token_handler=ServiceTokenHandlerConfig(_Handler),
            token_extractors=(),
        )


def test_it_refuses_an_unknown_extractor() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = AccessTokenConfig(
            token_handler=ServiceTokenHandlerConfig(_Handler),
            token_extractors=("cookie",),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]  -- a bad name is rejected at runtime
        )

"""The access-token authenticator configuration validates its extractors."""

from __future__ import annotations

import pytest

from xtr_security.bundle import AccessTokenConfig, ServiceTokenHandlerConfig
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
            token_extractors=("cookie",),
        )

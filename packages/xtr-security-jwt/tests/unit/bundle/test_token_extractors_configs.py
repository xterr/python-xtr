"""The token-extractor configurations default to a header-only reading."""

from __future__ import annotations

from xtr_security_jwt.bundle.token_extractors_configs import (
    AuthorizationHeaderExtractorConfig,
    CookieExtractorConfig,
    QueryParameterExtractorConfig,
    SplitCookieExtractorConfig,
    TokenExtractorsConfig,
)


def test_the_header_extractor_is_on_by_default() -> None:
    header = AuthorizationHeaderExtractorConfig()

    assert header.enabled is True
    assert header.prefix == "Bearer"
    assert header.name == "Authorization"


def test_the_cookie_extractor_is_off_by_default() -> None:
    cookie = CookieExtractorConfig()

    assert cookie.enabled is False
    assert cookie.name == "BEARER"


def test_the_query_extractor_is_off_by_default() -> None:
    query = QueryParameterExtractorConfig()

    assert query.enabled is False
    assert query.name == "bearer"


def test_the_split_cookie_extractor_is_off_by_default() -> None:
    split = SplitCookieExtractorConfig()

    assert split.enabled is False
    assert split.cookies == ()


def test_the_group_enables_only_the_header_by_default() -> None:
    config = TokenExtractorsConfig()

    assert config.authorization_header.enabled is True
    assert config.cookie.enabled is False
    assert config.query_parameter.enabled is False
    assert config.split_cookie.enabled is False

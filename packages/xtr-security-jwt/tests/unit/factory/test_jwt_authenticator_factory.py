"""The authenticator factory reports its contract and registers the extractor logic."""

from __future__ import annotations

from xtr_security_jwt.bundle.jwt_authenticator_config import JwtAuthenticatorConfig
from xtr_security_jwt.bundle.token_extractors_configs import (
    AuthorizationHeaderExtractorConfig,
    CookieExtractorConfig,
    QueryParameterExtractorConfig,
    SplitCookieExtractorConfig,
    TokenExtractorsConfig,
)
from xtr_security_jwt.factory.jwt_authenticator_factory import (
    JwtAuthenticatorFactory,
    _extractors_from,
)
from xtr_security_jwt.token_extractor.authorization_header_token_extractor import (
    AuthorizationHeaderTokenExtractor,
)
from xtr_security_jwt.token_extractor.cookie_token_extractor import CookieTokenExtractor
from xtr_security_jwt.token_extractor.query_parameter_token_extractor import (
    QueryParameterTokenExtractor,
)
from xtr_security_jwt.token_extractor.split_cookie_extractor import SplitCookieExtractor


def test_it_names_the_jwt_key_and_the_config() -> None:
    factory = JwtAuthenticatorFactory()

    assert factory.key == "jwt"
    assert factory.priority == 100
    assert factory.config_type is JwtAuthenticatorConfig


def test_the_default_extractors_are_the_header_alone() -> None:
    extractors = _extractors_from(TokenExtractorsConfig())

    assert len(extractors) == 1
    assert isinstance(extractors[0], AuthorizationHeaderTokenExtractor)


def test_every_enabled_extractor_is_built_in_the_fixed_order() -> None:
    config = TokenExtractorsConfig(
        authorization_header=AuthorizationHeaderExtractorConfig(enabled=True),
        query_parameter=QueryParameterExtractorConfig(enabled=True),
        cookie=CookieExtractorConfig(enabled=True),
        split_cookie=SplitCookieExtractorConfig(enabled=True, cookies=("h", "p")),
    )

    extractors = _extractors_from(config)

    assert [type(one) for one in extractors] == [
        AuthorizationHeaderTokenExtractor,
        QueryParameterTokenExtractor,
        CookieTokenExtractor,
        SplitCookieExtractor,
    ]

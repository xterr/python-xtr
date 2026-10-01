"""The JWT configuration defaults, validates and refuses bad values."""

from __future__ import annotations

import pytest
from xtr_security_core.exception import InvalidArgumentError

from xtr_security_jwt.bundle.encoder_config import EncoderConfig
from xtr_security_jwt.bundle.jwt_config import JwtConfig
from xtr_security_jwt.bundle.token_extractors_configs import TokenExtractorsConfig


def test_it_is_buildable_with_no_arguments() -> None:
    config = JwtConfig()

    assert config.secret_key is None
    assert config.token_ttl == 3600
    assert config.allow_no_expiration is False
    assert config.clock_skew == 0
    assert config.user_id_claim == "username"
    assert config.encoder.signature_algorithm == "RS256"
    assert isinstance(config.token_extractors, TokenExtractorsConfig)


def test_the_default_extractors_match_the_reference() -> None:
    extractors = JwtConfig().token_extractors

    assert extractors.authorization_header.enabled is True
    assert extractors.authorization_header.prefix == "Bearer"
    assert extractors.authorization_header.name == "Authorization"
    assert extractors.cookie.enabled is False
    assert extractors.cookie.name == "BEARER"
    assert extractors.query_parameter.enabled is False
    assert extractors.query_parameter.name == "bearer"
    assert extractors.split_cookie.enabled is False
    assert extractors.split_cookie.cookies == ()


def test_a_negative_clock_skew_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = JwtConfig(clock_skew=-1)


def test_a_non_positive_ttl_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = JwtConfig(token_ttl=0)


def test_an_empty_user_id_claim_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = JwtConfig(user_id_claim="")


def test_the_encoder_refuses_an_unsupported_algorithm() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = EncoderConfig(signature_algorithm="none")


def test_a_secret_key_is_kept() -> None:
    assert JwtConfig(secret_key="pem").secret_key == "pem"

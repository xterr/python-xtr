"""The encoder configuration defaults sanely and refuses an unknown algorithm."""

from __future__ import annotations

from typing import cast

import pytest
from xtr_security_core.exception import InvalidArgumentError

from xtr_security_jwt.bundle.encoder_config import EncoderConfig
from xtr_security_jwt.encoder.default_jwt_encoder import DefaultJwtEncoder


def test_it_builds_with_no_arguments() -> None:
    config = EncoderConfig()

    assert config.service is None
    assert config.signature_algorithm == "RS256"


def test_it_accepts_a_supported_algorithm() -> None:
    assert EncoderConfig(signature_algorithm="ES256").signature_algorithm == "ES256"


def test_it_refuses_an_unsupported_algorithm() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = EncoderConfig(signature_algorithm="none")


def test_it_accepts_an_encoder_service_implementing_the_interface() -> None:
    assert EncoderConfig(service=DefaultJwtEncoder).service is DefaultJwtEncoder


def test_it_refuses_an_encoder_service_that_is_not_an_encoder() -> None:
    class _NotAnEncoder: ...

    with pytest.raises(InvalidArgumentError):
        _ = EncoderConfig(service=_NotAnEncoder)


def test_it_refuses_an_encoder_service_that_is_not_a_class() -> None:
    # A name written where a class belongs would reach issubclass and raise a
    # TypeError nobody configured for; the configuration names it instead.
    with pytest.raises(InvalidArgumentError):
        _ = EncoderConfig(service=cast("type", cast("object", "DefaultJwtEncoder")))


def test_it_refuses_an_encoder_service_given_as_an_instance() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = EncoderConfig(service=cast("type", object()))

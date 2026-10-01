"""The encoder configuration defaults sanely and refuses an unknown algorithm."""

from __future__ import annotations

import pytest
from xtr_security_core.exception import InvalidArgumentError

from xtr_security_jwt.bundle.encoder_config import EncoderConfig


def test_it_builds_with_no_arguments() -> None:
    config = EncoderConfig()

    assert config.service is None
    assert config.signature_algorithm == "RS256"


def test_it_accepts_a_supported_algorithm() -> None:
    assert EncoderConfig(signature_algorithm="ES256").signature_algorithm == "ES256"


def test_it_refuses_an_unsupported_algorithm() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = EncoderConfig(signature_algorithm="none")

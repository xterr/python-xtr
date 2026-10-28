"""The generator that mints values no URI has to encode."""

from __future__ import annotations

import pytest

from xtr_security_csrf import InvalidArgumentError, TokenGeneratorInterface, UriSafeTokenGenerator

_URI_SAFE = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")


def test_it_answers_the_generator_contract() -> None:
    assert isinstance(UriSafeTokenGenerator(), TokenGeneratorInterface)


def test_it_mints_a_value_no_uri_has_to_encode() -> None:
    token = UriSafeTokenGenerator().generate_token()

    assert token
    assert set(token) <= _URI_SAFE


def test_it_mints_a_value_of_the_entropy_it_was_given() -> None:
    # 256 bits are 32 bytes, which base64 spells in 43 unpadded characters.
    assert len(UriSafeTokenGenerator().generate_token()) == 43


def test_it_mints_a_different_value_every_time() -> None:
    generator = UriSafeTokenGenerator()

    assert generator.generate_token() != generator.generate_token()


def test_it_refuses_entropy_shorter_than_a_byte() -> None:
    with pytest.raises(InvalidArgumentError, match="greater than 7"):
        _ = UriSafeTokenGenerator(entropy=7)

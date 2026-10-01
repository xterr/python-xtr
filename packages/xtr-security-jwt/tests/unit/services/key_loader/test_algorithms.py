"""The algorithm table maps each supported algorithm to its JWK key type."""

from __future__ import annotations

import pytest
from xtr_security_core.exception import InvalidArgumentError

from xtr_security_jwt.services.key_loader._algorithms import (
    ALLOWED_ALGORITHMS,
    HMAC_ALGORITHMS,
    key_type_for_algorithm,
)


def test_the_unsigned_algorithm_is_never_allowed() -> None:
    assert "none" not in ALLOWED_ALGORITHMS


def test_the_hmac_algorithms_are_a_subset_of_the_allowed_ones() -> None:
    assert HMAC_ALGORITHMS <= ALLOWED_ALGORITHMS


@pytest.mark.parametrize(
    ("algorithm", "key_type"),
    [
        ("RS256", "RSA"),
        ("PS512", "RSA"),
        ("ES256", "EC"),
        ("EdDSA", "OKP"),
        ("HS256", "oct"),
    ],
)
def test_it_maps_an_algorithm_to_its_key_type(algorithm: str, key_type: str) -> None:
    assert key_type_for_algorithm(algorithm) == key_type


def test_an_unsupported_algorithm_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = key_type_for_algorithm("none")

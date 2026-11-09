"""The token hash is the left half of a token's digest, picked by the signature algorithm."""

from __future__ import annotations

import pytest

from xtr_security_openid_connect_server.exception import UnsupportedAlgorithmError
from xtr_security_openid_connect_server.token_hash import token_hash

# The access token of an example in OpenID Connect Core 1.0, whose ID token
# carries the RS256 hash below as its at_hash. The other hashes of it are the
# same definition worked out once with another digest and written down, never
# recomputed here: a test that derived them would only repeat the code under
# test.
_ACCESS_TOKEN = "jHkWEdUXMU1BwAsC4vtUsZwnNvTIxEl0z9K3vx5KF0Y"

# The access token of the example in the OpenID Connect Token Hash Algorithm
# Implementer's Guide 1.0, which publishes its at_hash for an EdDSA ID token
# over each curve: the length of the Ed448 digest is pinned by a source of its
# own, not by the code under test.
_GUIDE_TOKEN = "YmJiZTAwYmYtMzgyOC00NzhkLTkyOTItNjJjNDM3MGYzOWIy9sFhvH8K_x8UIHj1osisS57f5DduL"


@pytest.mark.parametrize(
    ("algorithm", "expected"),
    [
        ("RS256", "77QmUPtjPfzWtF2AnpK9RQ"),
        ("ES384", "jtAeDp945y1dDqU3nkIVGNZP1HjH_MFs"),
        ("PS512", "q7nS86GgvvFaZkzALLWqJYaJIKw2wCDAVfCAsm5CrBM"),
        ("EdDSA", "q7nS86GgvvFaZkzALLWqJYaJIKw2wCDAVfCAsm5CrBM"),
    ],
)
def test_it_is_the_left_half_of_the_digest_the_algorithm_signs_with(
    algorithm: str,
    expected: str,
) -> None:
    assert token_hash(_ACCESS_TOKEN, algorithm) == expected


@pytest.mark.parametrize(
    ("curve", "expected"),
    [
        ("Ed25519", "q7nS86GgvvFaZkzALLWqJYaJIKw2wCDAVfCAsm5CrBM"),
        ("Ed448", "W6Ie3EoycJT-JESJ2WSAWX7LRP3FuHvmvNycBMeL-NngYGhJXChp7YRUBdOXcrKGZD4qnhCAstjO"),
    ],
)
def test_an_eddsa_token_is_hashed_with_the_digest_its_curve_signs_with(
    curve: str,
    expected: str,
) -> None:
    assert token_hash(_ACCESS_TOKEN, "EdDSA", curve) == expected


@pytest.mark.parametrize(
    ("curve", "expected"),
    [
        ("Ed25519", "p2LHG4H-8pYDc0hyVOo3iIHvZJUqe9tbj3jESOuXbkY"),
        ("Ed448", "sB_U72jyb0WgtX8TsVoqJnm6CD295W9gfSDRxkilB3LAL7REi9JYutRW_s1yE4lD8cOfMZf83gi4"),
    ],
)
def test_an_eddsa_token_hashes_as_the_implementers_guide_publishes(
    curve: str,
    expected: str,
) -> None:
    assert token_hash(_GUIDE_TOKEN, "EdDSA", curve) == expected


def test_a_curve_is_not_read_for_an_algorithm_naming_its_digest() -> None:
    assert token_hash(_ACCESS_TOKEN, "ES384", "P-384") == "jtAeDp945y1dDqU3nkIVGNZP1HjH_MFs"


def test_an_algorithm_naming_no_digest_is_refused_by_name() -> None:
    with pytest.raises(UnsupportedAlgorithmError, match=r"HS1"):
        _ = token_hash("x", "HS1")


def test_an_eddsa_curve_naming_no_digest_is_refused_by_name() -> None:
    with pytest.raises(UnsupportedAlgorithmError, match=r"X25519"):
        _ = token_hash("x", "EdDSA", "X25519")

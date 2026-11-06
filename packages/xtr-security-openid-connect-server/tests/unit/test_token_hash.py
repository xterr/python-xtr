"""The token hash is the left half of a token's digest, picked by the signature algorithm."""

from __future__ import annotations

import pytest

from xtr_security_openid_connect_server.exception import UnsupportedAlgorithmError
from xtr_security_openid_connect_server.token_hash import token_hash

# The access token of an example in OpenID Connect Core 1.0, whose ID token
# carries the RS256 hash below as its at_hash. The other three hashes are the
# same definition worked out once with another digest and written down, never
# recomputed here: a test that derived them would only repeat the code under
# test.
_ACCESS_TOKEN = "jHkWEdUXMU1BwAsC4vtUsZwnNvTIxEl0z9K3vx5KF0Y"


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


def test_an_algorithm_naming_no_digest_is_refused_by_name() -> None:
    with pytest.raises(UnsupportedAlgorithmError, match=r"HS1"):
        _ = token_hash("x", "HS1")

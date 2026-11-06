"""An algorithm a token hash cannot be taken for is reported by name."""

from __future__ import annotations

import pytest

from xtr_security_openid_connect_server.exception import (
    OpenIdConnectServerError,
    UnsupportedAlgorithmError,
)


def test_one_except_for_this_package_catches_it() -> None:
    with pytest.raises(OpenIdConnectServerError, match=r'"HS1"'):
        raise UnsupportedAlgorithmError("HS1")


def test_it_carries_the_algorithm_it_was_raised_for() -> None:
    error = UnsupportedAlgorithmError("HS1")

    assert error.algorithm == "HS1"

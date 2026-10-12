"""How a protected route reads a token presented to it."""

from __future__ import annotations

from datetime import timedelta

import pytest

from xtr_security_oauth2_server.bundle.resource_server_config import ResourceServerConfig
from xtr_security_oauth2_server.exception import InvalidConfigurationError


def test_a_negative_leeway_is_refused() -> None:
    # Leeway widens the window a token is accepted in.
    with pytest.raises(InvalidConfigurationError, match=r"jwt_leeway"):
        _ = ResourceServerConfig(jwt_leeway=timedelta(seconds=-1))


def test_no_leeway_is_the_default() -> None:
    assert ResourceServerConfig().jwt_leeway is None

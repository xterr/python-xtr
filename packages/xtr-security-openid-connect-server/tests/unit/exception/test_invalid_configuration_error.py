"""The refusal a deployment's own mistake is reported as."""

from __future__ import annotations

import pytest
from xtr_security_oauth2_server_core.exception import OAuthServerError

from xtr_security_openid_connect_server.exception import OpenIdConnectServerError
from xtr_security_openid_connect_server.exception.invalid_configuration_error import (
    InvalidConfigurationError,
)


def test_one_except_for_this_package_catches_it() -> None:
    with pytest.raises(OpenIdConnectServerError, match=r"name the setting"):
        raise InvalidConfigurationError("name the setting")


def test_a_configuration_this_package_cannot_read_is_a_bad_argument() -> None:
    with pytest.raises(ValueError, match=r"name the setting"):
        raise InvalidConfigurationError("name the setting")


def test_it_is_not_a_refusal_a_client_is_waiting_for() -> None:
    # No client caused this and no client is waiting for it, so no endpoint
    # may answer it as a protocol error.
    assert not issubclass(InvalidConfigurationError, OAuthServerError)

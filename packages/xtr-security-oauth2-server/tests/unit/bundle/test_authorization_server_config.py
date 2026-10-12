"""What the authorization server is described by: its shape, and what it refuses.

Presence is not checked here — a setting only the deployment can supply is
reported by the service that cannot be built without it — so what is left is
shape: a name that is not an origin, a lifetime that has already run out, a
wait that is negative, an algorithm that is no algorithm.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from xtr_security_oauth2_server.bundle.authorization_server_config import (
    AuthorizationServerConfig,
)
from xtr_security_oauth2_server.exception import InvalidConfigurationError


def test_an_issuer_carrying_a_path_is_refused() -> None:
    # The discovery document lives at a fixed path under the issuer.
    with pytest.raises(InvalidConfigurationError, match=r"not an origin"):
        _ = AuthorizationServerConfig(issuer="https://auth.test/oauth")


def test_an_issuer_that_is_only_a_host_is_refused() -> None:
    with pytest.raises(InvalidConfigurationError, match=r"not an origin"):
        _ = AuthorizationServerConfig(issuer="auth.test")


def test_an_origin_is_accepted_as_an_issuer() -> None:
    assert AuthorizationServerConfig(issuer="https://auth.test").issuer == "https://auth.test"


def test_an_access_token_lifetime_that_is_not_positive_is_refused() -> None:
    # A credential already expired when it is issued can never be used.
    with pytest.raises(InvalidConfigurationError, match=r"authorization_server\.access_token_ttl"):
        _ = AuthorizationServerConfig(access_token_ttl=timedelta(0))


def test_a_refresh_token_lifetime_that_is_not_positive_is_refused() -> None:
    with pytest.raises(
        InvalidConfigurationError,
        match=r"authorization_server\.refresh_token_ttl",
    ):
        _ = AuthorizationServerConfig(refresh_token_ttl=timedelta(0))


def test_an_authorization_code_lifetime_that_is_not_positive_is_refused() -> None:
    with pytest.raises(InvalidConfigurationError, match=r"authorization_server\.auth_code_ttl"):
        _ = AuthorizationServerConfig(auth_code_ttl=timedelta(seconds=-1))


def test_a_device_code_lifetime_that_is_not_positive_is_refused() -> None:
    with pytest.raises(InvalidConfigurationError, match=r"authorization_server\.device_code_ttl"):
        _ = AuthorizationServerConfig(device_code_ttl=timedelta(0))


def test_a_negative_polling_interval_is_refused() -> None:
    with pytest.raises(InvalidConfigurationError, match=r"device_code_polling_interval"):
        _ = AuthorizationServerConfig(device_code_polling_interval=-1)


def test_an_empty_signature_algorithm_is_refused() -> None:
    with pytest.raises(InvalidConfigurationError, match=r"signature_algorithm is empty"):
        _ = AuthorizationServerConfig(signature_algorithm="")

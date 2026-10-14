from __future__ import annotations

import re

import pytest

from xtr_http_client.bundle import (
    ClientOptionsConfig,
    HttpClientConfig,
    RetryFailedConfig,
    ScopedClientConfig,
)
from xtr_http_client.exception import InvalidArgumentError


def test_it_builds_with_no_arguments() -> None:
    config = HttpClientConfig()

    assert config.scoped_clients == {}
    assert not config.mock_response_factory
    assert not config.tracing


def test_a_scoped_client_needs_a_name() -> None:
    with pytest.raises(InvalidArgumentError, match="needs a name"):
        _ = HttpClientConfig(scoped_clients={"": ScopedClientConfig(base_uri="https://api.test/")})


def test_a_scoped_client_with_no_base_uri_cannot_inherit_fallback_base_uris() -> None:
    defaults = ClientOptionsConfig(
        retry_failed=RetryFailedConfig(enabled=True, base_uris=("https://fallback.test/",))
    )

    with pytest.raises(InvalidArgumentError, match=re.escape('"retry_failed.base_uris"')):
        _ = HttpClientConfig(
            default_options=defaults,
            scoped_clients={"api": ScopedClientConfig(scope=r"https://api\.test/")},
        )

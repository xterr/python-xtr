from __future__ import annotations

import re

import pytest

from xtr_http_client.bundle import ClientOptionsConfig, RetryFailedConfig, ScopedClientConfig
from xtr_http_client.exception import InvalidArgumentError

_BASE_URI = "https://api.test/"
_FALLBACK = "https://fallback.test/"


def test_a_client_names_a_scope_or_a_base_uri() -> None:
    with pytest.raises(
        InvalidArgumentError,
        match=re.escape('Either "scope" or "base_uri" should be defined.'),
    ):
        _ = ScopedClientConfig()


def test_a_query_needs_a_base_uri_to_apply_to() -> None:
    with pytest.raises(
        InvalidArgumentError,
        match=re.escape('"query" applies to "base_uri" but no base URI is defined.'),
    ):
        _ = ScopedClientConfig(scope=r"https://api\.test/", query={"page": 1})


def test_fallback_base_uris_need_a_base_uri_to_fall_back_from() -> None:
    retries = RetryFailedConfig(enabled=True, base_uris=(_FALLBACK,))

    with pytest.raises(InvalidArgumentError, match=re.escape('"retry_failed.base_uris"')):
        _ = ScopedClientConfig(scope=r"https://api\.test/", retry_failed=retries)


def test_its_options_carry_where_it_is_and_its_credentials() -> None:
    config = ScopedClientConfig(
        scope=r"https://api\.test/",
        base_uri=_BASE_URI,
        auth_bearer="t0ken",
        query={"page": 1},
        timeout=5.0,
        mock_response_factory=True,
        rate_limiter="api",
    )

    assert config.to_options() == {
        "timeout": 5.0,
        "base_uri": _BASE_URI,
        "auth_bearer": "t0ken",
        "query": {"page": 1},
    }


def test_its_credentials_are_kept_out_of_the_repr() -> None:
    config = ScopedClientConfig(base_uri=_BASE_URI, auth_basic="user:s3cret", auth_bearer="t0ken")

    assert "s3cret" not in repr(config)
    assert "t0ken" not in repr(config)


def test_the_retries_and_the_limiter_it_leaves_unset_are_the_defaults() -> None:
    defaults = ClientOptionsConfig(retry_failed=RetryFailedConfig(enabled=True), rate_limiter="api")

    inherited = ScopedClientConfig(base_uri=_BASE_URI).inheriting(defaults)

    assert inherited.retry_failed == defaults.retry_failed
    assert inherited.rate_limiter == "api"


def test_its_own_retries_and_limiter_win_over_the_defaults() -> None:
    own = RetryFailedConfig(enabled=True, max_retries=1)
    defaults = ClientOptionsConfig(retry_failed=RetryFailedConfig(enabled=True), rate_limiter="api")

    inherited = ScopedClientConfig(
        base_uri=_BASE_URI, retry_failed=own, rate_limiter="own"
    ).inheriting(defaults)

    assert inherited.retry_failed == own
    assert inherited.rate_limiter == "own"

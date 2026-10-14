from __future__ import annotations

import re
from dataclasses import replace

import pytest

from xtr_http_client.bundle import RetryFailedConfig
from xtr_http_client.exception import InvalidArgumentError

_TUNED_WITH_A_SERVICE = re.escape(
    'The "retry_strategy" option cannot be used along with the "http_codes", "delay", '
    '"multiplier", "max_delay" or "jitter" options.'
)


def test_it_builds_with_no_arguments_and_retries_nothing() -> None:
    assert not RetryFailedConfig().enabled


def test_fallback_base_uris_need_retries_to_be_enabled() -> None:
    with pytest.raises(
        InvalidArgumentError,
        match=re.escape('The "base_uris" option requires retries to be enabled.'),
    ):
        _ = RetryFailedConfig(base_uris=("https://fallback.test/",))


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("http_codes", {500: None}),
        ("delay", 0),
        ("multiplier", 3.0),
        ("max_delay", 10),
        ("jitter", 0.0),
    ],
)
def test_a_strategy_service_is_not_tuned_by_the_numbers_it_ignores(
    option: str, value: object
) -> None:
    named = RetryFailedConfig(enabled=True, retry_strategy="custom")

    with pytest.raises(InvalidArgumentError, match=_TUNED_WITH_A_SERVICE):
        _ = replace(named, **{option: value})


def test_a_strategy_service_takes_how_many_retries_there_are() -> None:
    config = RetryFailedConfig(enabled=True, max_retries=5, retry_strategy="custom")

    assert config.max_retries == 5

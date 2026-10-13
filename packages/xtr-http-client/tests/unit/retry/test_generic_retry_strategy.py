from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.fake_response import FakeResponse
from xtr_http_client.exception import InvalidArgumentError, TransportError
from xtr_http_client.internal.option_merge import as_options
from xtr_http_client.retry import (
    DEFAULT_RETRY_STATUS_CODES,
    IDEMPOTENT_METHODS,
    GenericRetryStrategy,
    RetryContext,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

pytestmark = pytest.mark.anyio

_URL = "http://example.com/"


def _unanswered(retry_count: int, method: str = "GET") -> RetryContext:
    """An attempt nothing came back from."""
    return RetryContext(method, _URL, as_options({}), retry_count, None)


def _answer(status_code: int, method: str) -> FakeResponse:
    return FakeResponse(status_code=status_code, method=method, url=_URL)


def _answered(response: FakeResponse, method: str, retry_count: int = 0) -> RetryContext:
    return RetryContext(method, _URL, as_options({}), retry_count, response)


@pytest.mark.parametrize(
    ("method", "status_code", "error"),
    [
        ("GET", 200, TransportError("nothing came back")),
        ("GET", 500, None),
        ("POST", 429, None),
    ],
)
async def test_what_the_default_list_retries(
    method: str,
    status_code: int,
    error: TransportError | None,
) -> None:
    strategy = GenericRetryStrategy()

    async with _answer(status_code, method) as response:
        assert await strategy.should_retry(_answered(response, method), None, error) is True


@pytest.mark.parametrize(
    ("method", "status_code", "error"),
    [
        ("POST", 200, None),
        ("POST", 200, TransportError("nothing came back")),
        ("POST", 500, None),
    ],
)
async def test_what_the_default_list_does_not_retry(
    method: str,
    status_code: int,
    error: TransportError | None,
) -> None:
    strategy = GenericRetryStrategy()

    async with _answer(status_code, method) as response:
        assert await strategy.should_retry(_answered(response, method), None, error) is False


async def test_an_attempt_nothing_came_back_from_is_retried_for_an_idempotent_method() -> None:
    strategy = GenericRetryStrategy()
    error = TransportError("nothing came back")

    assert await strategy.should_retry(_unanswered(0, "GET"), None, error) is True
    assert await strategy.should_retry(_unanswered(0, "POST"), None, error) is False


async def test_a_list_naming_no_transport_failure_never_retries_one() -> None:
    strategy = GenericRetryStrategy([500])

    assert await strategy.should_retry(_unanswered(0, "GET"), None, TransportError("gone")) is False


async def test_a_bare_sequence_of_codes_retries_every_method() -> None:
    strategy = GenericRetryStrategy([500])

    async with _answer(500, "POST") as response:
        assert await strategy.should_retry(_answered(response, "POST"), None, None) is True


async def test_a_mapping_retries_a_code_only_for_the_methods_it_names() -> None:
    strategy = GenericRetryStrategy({500: ("POST",)})

    async with _answer(500, "POST") as allowed:
        assert await strategy.should_retry(_answered(allowed, "POST"), None, None) is True
    async with _answer(500, "GET") as refused:
        assert await strategy.should_retry(_answered(refused, "GET"), None, None) is False


async def test_the_body_is_never_what_this_strategy_decides_on() -> None:
    strategy = GenericRetryStrategy()

    async with _answer(500, "GET") as response:
        assert await strategy.should_retry(_answered(response, "GET"), b"anything", None) is True


@pytest.mark.parametrize(
    ("delay_ms", "multiplier", "max_delay_ms", "retry_count", "expected"),
    [
        (1000, 1, 5000, 0, 1000),
        (1000, 1, 5000, 1, 1000),
        (1000, 1, 5000, 2, 1000),
        (1000, 2, 10000, 0, 1000),
        (1000, 2, 10000, 1, 2000),
        (1000, 2, 10000, 2, 4000),
        (1000, 2, 10000, 3, 8000),
        (1000, 2, 10000, 4, 10000),
        (1000, 2, 0, 4, 16000),
        (1000, 3, 10000, 0, 1000),
        (1000, 3, 10000, 1, 3000),
        (1000, 3, 10000, 2, 9000),
        (1000, 1, 500, 0, 500),
        (0, 2, 10000, 0, 0),
        (0, 2, 10000, 1, 0),
    ],
)
def test_the_delay_grows_per_attempt_and_stops_at_the_ceiling(
    delay_ms: int,
    multiplier: int,
    max_delay_ms: int,
    retry_count: int,
    expected: int,
) -> None:
    strategy = GenericRetryStrategy([], delay_ms, multiplier, max_delay_ms, 0)

    assert strategy.get_delay(_unanswered(retry_count), None, None) == expected


@pytest.mark.parametrize(("multiplier", "retry_count"), [(1, 0), (1.1, 2)])
def test_jitter_spreads_the_delay_over_a_window_around_it(
    multiplier: float,
    retry_count: int,
) -> None:
    bounds: list[tuple[float, float]] = []

    def lowest(low: float, high: float) -> float:
        bounds.append((low, high))

        return low

    def highest(low: float, high: float) -> float:
        bounds.append((low, high))

        return high

    plain = GenericRetryStrategy([], 1000, multiplier, 0, 0).get_delay(
        _unanswered(retry_count), None, None
    )
    low = GenericRetryStrategy([], 1000, multiplier, 0, 1, lowest).get_delay(
        _unanswered(retry_count), None, None
    )
    high = GenericRetryStrategy([], 1000, multiplier, 0, 1, highest).get_delay(
        _unanswered(retry_count), None, None
    )

    assert bounds == [(-plain, plain), (-plain, plain)]
    assert low == 0
    assert high == 2 * plain


def test_a_delay_is_left_alone_when_no_jitter_is_asked_for() -> None:
    def never(low: float, high: float) -> float:
        del low, high
        raise AssertionError("the delay was spread although no jitter was asked for")

    strategy = GenericRetryStrategy([], 1000, 1, 0, 0, never)

    assert strategy.get_delay(_unanswered(0), None, None) == 1000


def test_the_default_list_names_the_methods_a_server_answers_the_same_way() -> None:
    listed: Mapping[int, Sequence[str] | None] = DEFAULT_RETRY_STATUS_CODES

    assert listed[500] == IDEMPOTENT_METHODS
    assert listed[503] is None
    assert listed[0] == IDEMPOTENT_METHODS


@pytest.mark.parametrize(
    ("build", "message"),
    [
        (
            lambda: GenericRetryStrategy(delay_ms=-1),
            'Delay must be greater than or equal to zero: "-1" given.',
        ),
        (
            lambda: GenericRetryStrategy(multiplier=0.5),
            'Multiplier must be greater than or equal to one: "0.5" given.',
        ),
        (
            lambda: GenericRetryStrategy(max_delay_ms=-1),
            'Max delay must be greater than or equal to zero: "-1" given.',
        ),
        (
            lambda: GenericRetryStrategy(jitter=-0.1),
            'Jitter must be between 0 and 1: "-0.1" given.',
        ),
        (
            lambda: GenericRetryStrategy(jitter=1.5),
            'Jitter must be between 0 and 1: "1.5" given.',
        ),
    ],
)
def test_a_delay_nobody_could_have_meant_is_refused(
    build: Callable[[], GenericRetryStrategy],
    message: str,
) -> None:
    with pytest.raises(InvalidArgumentError) as refused:
        _ = build()

    assert str(refused.value) == message

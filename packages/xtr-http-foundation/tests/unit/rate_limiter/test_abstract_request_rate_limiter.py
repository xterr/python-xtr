"""The counting, the looking ahead and the forgetting a request limiter shares."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override
from xtr_http_message import ServerRequest

from xtr_http_foundation import (
    AbstractRequestRateLimiter,
    PeekableRequestRateLimiterInterface,
    RateLimiterInterface,
    RequestRateLimiterInterface,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_http_message_contracts import ServerRequestInterface

_SOON = datetime(2035, 1, 1, tzinfo=UTC)
_LATER = datetime(2036, 1, 1, tzinfo=UTC)


@final
class _Limit:
    """A limit as one consumption left it, built to be told apart from another."""

    __slots__ = ("_accepted", "_remaining", "_retry_after")

    def __init__(self, *, accepted: bool, remaining: int, retry_after: datetime) -> None:
        self._accepted = accepted
        self._remaining = remaining
        self._retry_after = retry_after

    def is_accepted(self) -> bool:
        return self._accepted

    @property
    def remaining_tokens(self) -> int:
        return self._remaining

    @property
    def retry_after(self) -> datetime:
        return self._retry_after

    @property
    def limit(self) -> int:
        return 5

    @property
    def reset_at(self) -> datetime | None:
        return None


@final
class _Counter:
    """A counter that answers with the limit it was given and records what it was asked."""

    __slots__ = ("asked", "limit", "resets")

    def __init__(self, limit: _Limit) -> None:
        self.limit = limit
        self.asked: list[int] = []
        self.resets = 0

    async def consume(self, tokens: int = 1) -> _Limit:
        self.asked.append(tokens)
        return self.limit

    async def reset(self) -> None:
        self.resets += 1


@final
class _Limiter(AbstractRequestRateLimiter):
    """A request limiter counting under the counters it was given."""

    def __init__(self, counters: Sequence[_Counter]) -> None:
        self._counters = tuple(counters)

    @override
    def get_limiters(self, request: ServerRequestInterface) -> Sequence[RateLimiterInterface]:
        return self._counters


def test_it_refuses_to_be_built_without_saying_what_a_request_counts_under() -> None:
    incomplete = type("Incomplete", (AbstractRequestRateLimiter,), {})

    with pytest.raises(TypeError):
        # Building the half-written limiter is the case under test.
        _ = incomplete()  # ty: ignore[call-non-callable]


def test_a_request_limiter_answers_both_contracts() -> None:
    limiter = _Limiter([])

    assert isinstance(limiter, PeekableRequestRateLimiterInterface)
    assert isinstance(limiter, RequestRateLimiterInterface)


@pytest.mark.anyio
async def test_it_counts_a_request_once_under_every_limiter() -> None:
    counter = _Counter(_Limit(accepted=True, remaining=4, retry_after=_SOON))
    limiter = _Limiter([counter])

    limit = await limiter.consume(ServerRequest("GET", "/"))

    assert counter.asked == [1]
    assert limit is counter.limit


@pytest.mark.anyio
async def test_it_looks_ahead_without_counting_the_request() -> None:
    counter = _Counter(_Limit(accepted=True, remaining=4, retry_after=_SOON))
    limiter = _Limiter([counter])

    limit = await limiter.peek(ServerRequest("GET", "/"))

    assert counter.asked == [0]
    assert limit is counter.limit


@pytest.mark.anyio
async def test_it_answers_with_the_limit_that_was_not_accepted() -> None:
    granted = _Counter(_Limit(accepted=True, remaining=0, retry_after=_SOON))
    refused = _Counter(_Limit(accepted=False, remaining=9, retry_after=_LATER))
    limiter = _Limiter([granted, refused])

    limit = await limiter.consume(ServerRequest("GET", "/"))

    assert limit is refused.limit


@pytest.mark.anyio
async def test_it_answers_with_the_refused_limit_in_either_order() -> None:
    granted = _Counter(_Limit(accepted=True, remaining=0, retry_after=_SOON))
    refused = _Counter(_Limit(accepted=False, remaining=9, retry_after=_LATER))
    limiter = _Limiter([refused, granted])

    limit = await limiter.consume(ServerRequest("GET", "/"))

    assert limit is refused.limit


@pytest.mark.anyio
async def test_it_answers_with_the_limit_holding_less_when_both_were_accepted() -> None:
    richer = _Counter(_Limit(accepted=True, remaining=4, retry_after=_LATER))
    poorer = _Counter(_Limit(accepted=True, remaining=2, retry_after=_SOON))
    limiter = _Limiter([richer, poorer])

    limit = await limiter.consume(ServerRequest("GET", "/"))

    assert limit is poorer.limit


@pytest.mark.anyio
async def test_it_answers_with_the_limit_holding_less_whichever_order_they_come_in() -> None:
    richer = _Counter(_Limit(accepted=True, remaining=4, retry_after=_LATER))
    poorer = _Counter(_Limit(accepted=True, remaining=2, retry_after=_SOON))
    limiter = _Limiter([poorer, richer])

    limit = await limiter.consume(ServerRequest("GET", "/"))

    assert limit is poorer.limit


@pytest.mark.anyio
async def test_it_answers_with_the_limit_that_waits_longer_when_both_hold_the_same() -> None:
    sooner = _Counter(_Limit(accepted=True, remaining=2, retry_after=_SOON))
    later = _Counter(_Limit(accepted=True, remaining=2, retry_after=_LATER))
    limiter = _Limiter([sooner, later])

    limit = await limiter.consume(ServerRequest("GET", "/"))

    assert limit is later.limit


@pytest.mark.anyio
async def test_it_forgets_the_hits_counted_under_every_limiter() -> None:
    first = _Counter(_Limit(accepted=True, remaining=4, retry_after=_SOON))
    second = _Counter(_Limit(accepted=True, remaining=2, retry_after=_SOON))
    limiter = _Limiter([first, second])

    await limiter.reset(ServerRequest("GET", "/"))

    assert first.resets == 1
    assert second.resets == 1


@pytest.mark.anyio
async def test_it_answers_that_nothing_is_refused_when_a_request_counts_under_no_limiter() -> None:
    limiter = _Limiter([])

    limit = await limiter.consume(ServerRequest("GET", "/"))

    assert limit.is_accepted() is True
    assert limit.remaining_tokens == sys.maxsize
    assert limit.limit == sys.maxsize
    assert limit.reset_at is None
    assert datetime.now(UTC) >= limit.retry_after

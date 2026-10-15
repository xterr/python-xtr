"""A request limiter that looks ahead answers both contracts it could be read through."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from xtr_http_foundation import (
    PeekableRequestRateLimiterInterface,
    RequestRateLimiterInterface,
    RequestRateLimitInterface,
)

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface


class _Limit:
    """The state of a limit, as a counter that counts nothing leaves it."""

    def is_accepted(self) -> bool:
        return True

    @property
    def remaining_tokens(self) -> int:
        return 10

    @property
    def retry_after(self) -> datetime:
        return datetime(2035, 1, 1, tzinfo=UTC)

    @property
    def limit(self) -> int:
        return 10

    @property
    def reset_at(self) -> datetime | None:
        return None


class _PeekableLimiter:
    """A request limiter that reports its limit without counting."""

    async def consume(self, _request: ServerRequestInterface) -> RequestRateLimitInterface:
        return _Limit()

    async def reset(self, _request: ServerRequestInterface) -> None:
        return None

    async def peek(self, _request: ServerRequestInterface) -> RequestRateLimitInterface:
        return _Limit()


def test_a_peekable_limiter_answers_the_contract_of_looking_ahead() -> None:
    assert isinstance(_PeekableLimiter(), PeekableRequestRateLimiterInterface)


def test_a_peekable_limiter_answers_the_contract_of_counting() -> None:
    assert isinstance(_PeekableLimiter(), RequestRateLimiterInterface)


def test_a_limiter_that_cannot_look_ahead_does_not_answer_the_contract_of_looking_ahead() -> None:
    class _CountingOnly:
        """A request limiter that counts but never looks ahead."""

        async def consume(self, _request: ServerRequestInterface) -> RequestRateLimitInterface:
            return _Limit()

        async def reset(self, _request: ServerRequestInterface) -> None:
            return None

    assert not isinstance(_CountingOnly(), PeekableRequestRateLimiterInterface)

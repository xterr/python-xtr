"""A request limiter answers the contract its consumers read it through."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from xtr_http_foundation import RequestRateLimiterInterface, RequestRateLimitInterface

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


class _RequestLimiter:
    """A request limiter that counts nothing and forgets nothing."""

    async def consume(self, _request: ServerRequestInterface) -> RequestRateLimitInterface:
        return _Limit()

    async def reset(self, _request: ServerRequestInterface) -> None:
        return None


def test_a_request_limiter_answers_the_contract() -> None:
    assert isinstance(_RequestLimiter(), RequestRateLimiterInterface)


def test_an_object_of_no_members_does_not_answer_the_contract() -> None:
    assert not isinstance(object(), RequestRateLimiterInterface)

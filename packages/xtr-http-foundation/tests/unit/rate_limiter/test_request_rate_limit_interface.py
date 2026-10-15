"""A limit's state is read through the members this contract names."""

from __future__ import annotations

from datetime import UTC, datetime

from xtr_http_foundation import RequestRateLimitInterface


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


def test_a_limit_answers_the_contract() -> None:
    assert isinstance(_Limit(), RequestRateLimitInterface)


def test_an_object_of_no_members_does_not_answer_the_contract() -> None:
    assert not isinstance(object(), RequestRateLimitInterface)

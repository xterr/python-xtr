from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from typing import TYPE_CHECKING

from tests.support.fake_response import FakeResponse
from xtr_http_client.internal.retry_delay import retry_after_ms

if TYPE_CHECKING:
    from collections.abc import Sequence


def _answer(retry_after: str | None) -> FakeResponse:
    headers: dict[str, Sequence[str]] = (
        {} if retry_after is None else {"Retry-After": (retry_after,)}
    )

    return FakeResponse(status_code=503, headers=headers)


def test_no_header_leaves_the_wait_to_the_strategy() -> None:
    assert retry_after_ms(_answer(None)) is None


def test_a_number_of_seconds_is_read_as_one() -> None:
    assert retry_after_ms(_answer("12")) == 12000


def test_a_fraction_of_a_second_is_read_as_one() -> None:
    assert retry_after_ms(_answer("0.46")) == 460


def test_a_date_is_read_as_the_wait_until_it() -> None:
    when = datetime.now(UTC) + timedelta(seconds=30)

    waited = retry_after_ms(_answer(format_datetime(when, usegmt=True)))

    assert waited is not None
    assert 28000 <= waited <= 30000


def test_a_date_already_past_asks_for_no_wait() -> None:
    gone = datetime.fromtimestamp(time.time() - 600, tz=UTC)

    assert retry_after_ms(_answer(format_datetime(gone, usegmt=True))) == 0


def test_a_header_that_is_neither_leaves_the_wait_to_the_strategy() -> None:
    assert retry_after_ms(_answer("whenever you like")) is None


def test_a_wait_too_large_to_hold_leaves_it_to_the_strategy() -> None:
    assert retry_after_ms(_answer("inf")) is None

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, final

import pytest
from xtr_clock import MockClock
from xtr_http_message import Request
from xtr_rate_limiter import LimiterInterface, RateLimit, Reservation

from tests.support.fake_client import FakeClient
from xtr_http_client import MockHttpClient, MockResponse, ThrottlingHttpClient
from xtr_http_client.exception import TransportError

if TYPE_CHECKING:
    from xtr_http_client_contracts import HttpClientInterface, RequestOptions

pytestmark = pytest.mark.anyio

_URL = "http://example.com/foo-bar"


@final
class _Limiter:
    """Books a token due ``wait`` seconds on, and keeps what it was asked for.

    The clock it hands its reservations is the test's, so waiting moves that
    clock instead of the machine: a test proves a request waited by how far
    the clock went, and takes no time doing it.
    """

    def __init__(self, clock: MockClock, wait: float = 0.0) -> None:
        self.clock = clock
        self.wait = wait
        self.reservations: list[tuple[int, float | None]] = []
        self.resets = 0

    async def reserve(self, tokens: int = 1, max_time: float | None = None) -> Reservation:
        self.reservations.append((tokens, max_time))
        now = self.clock.now()

        return Reservation(
            now.timestamp() + self.wait,
            RateLimit(0, now, accepted=True, limit=1, clock=self.clock),
            clock=self.clock,
        )

    async def consume(self, tokens: int = 1) -> RateLimit:
        del tokens

        raise NotImplementedError

    async def reset(self) -> None:
        self.resets += 1


def _throttled(
    inner: HttpClientInterface | None = None,
    wait: float = 0.0,
) -> tuple[ThrottlingHttpClient, _Limiter]:
    """A paced client, with the limiter pacing it for the test to assert on."""
    limiter = _Limiter(MockClock(), wait)

    return ThrottlingHttpClient(inner if inner is not None else MockHttpClient(), limiter), limiter


def test_the_limiter_the_tests_pace_with_is_one() -> None:
    assert isinstance(_Limiter(MockClock()), LimiterInterface)


async def test_a_request_books_one_token_and_is_answered() -> None:
    client, limiter = _throttled(MockHttpClient(MockResponse(b"paced")))

    async with await client.request("GET", _URL) as response:
        assert await response.get_content() == b"paced"

    assert limiter.reservations == [(1, None)]


async def test_a_request_waits_for_the_moment_its_token_is_due() -> None:
    client, limiter = _throttled(wait=5.0)
    start = limiter.clock.now()

    async with await client.request("GET", _URL):
        pass

    assert (limiter.clock.now() - start).total_seconds() == 5.0


async def test_a_token_that_is_due_already_is_waited_on_and_no_time_passes() -> None:
    client, limiter = _throttled()
    start = limiter.clock.now()

    async with await client.request("GET", _URL):
        pass

    assert limiter.clock.now() == start


async def test_a_sent_request_books_a_token_and_waits_for_it_too() -> None:
    client, limiter = _throttled(wait=2.0)
    start = limiter.clock.now()

    async with await client.send_request(Request("GET", _URL)):
        pass

    assert limiter.reservations == [(1, None)]
    assert (limiter.clock.now() - start).total_seconds() == 2.0


async def test_every_request_books_a_token_of_its_own() -> None:
    inner = MockHttpClient([MockResponse(), MockResponse(), MockResponse()])
    client, limiter = _throttled(inner, 1.0)
    start = limiter.clock.now()

    for _ in range(3):
        async with await client.request("GET", _URL):
            pass

    assert limiter.reservations == [(1, None)] * 3
    assert (limiter.clock.now() - start).total_seconds() == 3.0
    assert inner.get_requests_count() == 3


async def test_the_request_the_wrapped_client_is_handed_is_the_one_that_was_asked_for() -> None:
    made: list[tuple[str, str, object]] = []

    def answer(method: str, url: str, options: RequestOptions) -> MockResponse:
        made.append((method, url, options.get("headers")))

        return MockResponse()

    client, _ = _throttled(MockHttpClient(answer))

    async with await client.request("POST", _URL, headers={"X-Paced": "yes"}):
        pass

    assert made == [("POST", _URL, {"X-Paced": "yes"})]


async def test_a_request_the_wrapped_client_cannot_answer_is_reported() -> None:
    client, limiter = _throttled(MockHttpClient([]))

    with pytest.raises(TransportError):
        _ = await client.request("GET", _URL)

    assert limiter.reservations == [(1, None)]


async def test_a_narrowed_client_is_paced_by_the_same_limiter() -> None:
    client, limiter = _throttled(MockHttpClient([MockResponse(), MockResponse()]), 1.0)

    narrowed = client.with_options(headers={"X-Paced": "yes"})
    async with await narrowed.request("GET", _URL):
        pass
    async with await client.request("GET", _URL):
        pass

    assert narrowed is not client
    assert narrowed._limiter is limiter
    assert limiter.reservations == [(1, None), (1, None)]


async def test_resetting_forgets_what_the_limiter_counted() -> None:
    client, limiter = _throttled()

    client.reset()
    await asyncio.sleep(0)

    assert limiter.resets == 1


def test_resetting_with_no_loop_to_run_on_resets_the_limiter_there_and_then() -> None:
    client, limiter = _throttled()

    client.reset()

    assert limiter.resets == 1


async def test_resetting_reaches_a_wrapped_client_that_can_be_reset() -> None:
    inner = MockHttpClient()
    client, limiter = _throttled(inner)

    async with await client.request("GET", _URL):
        pass
    client.reset()
    await asyncio.sleep(0)

    assert inner.get_requests_count() == 0
    assert limiter.resets == 1


async def test_resetting_leaves_a_wrapped_client_that_cannot_be_reset_alone() -> None:
    client, limiter = _throttled(FakeClient())

    async with await client.request("GET", _URL):
        pass
    client.reset()
    await asyncio.sleep(0)

    assert limiter.resets == 1

"""Throttling and rate limiting of :class:`AbstractTransport`."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typing_extensions import override
from xtr_clock import MockClock
from xtr_logging_contracts import AbstractLogger, Level
from xtr_mime import Address, RawMessage
from xtr_rate_limiter import (
    InMemoryStorage,
    LimiterConfig,
    RateLimiterFactory,
    RateLimitExceededError,
)

from tests.support.fake_transport import FakeTransport
from tests.support.recorded_events import recording_dispatcher
from xtr_mailer import Envelope
from xtr_mailer.event import FailedMessageEvent, MessageEvent
from xtr_mailer.transport import NullTransport

if TYPE_CHECKING:
    from xtr_logging_contracts import Context, LevelLike

pytestmark = pytest.mark.anyio

_MESSAGE = RawMessage(b"")


def _envelope() -> Envelope:
    return Envelope(Address("fabien@example.com"), [Address("helene@example.com")])


def _limited_to(limit: int) -> RateLimiterFactory:
    return RateLimiterFactory(
        "mailer",
        LimiterConfig("fixed_window", limit=limit, interval="1 hour"),
        InMemoryStorage(),
    )


class _RecordingLogger(AbstractLogger):
    def __init__(self) -> None:
        self.records: list[tuple[LevelLike, str, Context | None]] = []

    @override
    def log(self, level: LevelLike, message: str, /, context: Context | None = None) -> None:
        self.records.append((level, message, context))


async def test_sends_are_spaced_by_the_max_per_second() -> None:
    clock = MockClock()
    transport = NullTransport(clock=clock).set_max_per_second(2 / 10)
    start = clock.now().timestamp()

    elapsed: list[float] = []
    for _ in range(4):
        _ = await transport.send(_MESSAGE, _envelope())
        elapsed.append(clock.now().timestamp() - start)

    assert elapsed == pytest.approx([0, 5, 10, 15])


async def test_a_rate_of_zero_or_less_sends_at_once() -> None:
    clock = MockClock()
    transport = NullTransport(clock=clock).set_max_per_second(2 / 10)
    _ = await transport.send(_MESSAGE, _envelope())
    start = clock.now().timestamp()

    _ = transport.set_max_per_second(-3)
    _ = await transport.send(_MESSAGE, _envelope())
    _ = await transport.send(_MESSAGE, _envelope())

    assert clock.now().timestamp() - start == 0


async def test_changing_the_rate_starts_counting_afresh() -> None:
    clock = MockClock()
    transport = NullTransport(clock=clock).set_max_per_second(1 / 10)
    _ = await transport.send(_MESSAGE, _envelope())
    start = clock.now().timestamp()

    _ = transport.set_max_per_second(1 / 10)
    _ = await transport.send(_MESSAGE, _envelope())

    assert clock.now().timestamp() - start == 0


async def test_a_failed_send_waits_its_turn_once() -> None:
    clock = MockClock()
    transport = FakeTransport(clock=clock).set_max_per_second(1 / 10)
    transport.error = RuntimeError("down")
    for _ in range(2):
        with pytest.raises(RuntimeError):
            _ = await transport.send(_MESSAGE, _envelope())
    start = clock.now().timestamp()

    with pytest.raises(RuntimeError):
        _ = await transport.send(_MESSAGE, _envelope())

    assert clock.now().timestamp() - start == pytest.approx(10)


async def test_the_wait_is_logged_for_debugging() -> None:
    logger = _RecordingLogger()
    transport = NullTransport(logger=logger, clock=MockClock()).set_max_per_second(1 / 4)

    _ = await transport.send(_MESSAGE, _envelope())
    _ = await transport.send(_MESSAGE, _envelope())

    assert len(logger.records) == 1
    level, message, context = logger.records[0]
    assert level == Level.DEBUG
    assert message == 'Email transport "{transport}" sleeps for {seconds} seconds.'
    assert context is not None
    assert context["transport"] == "null://"
    assert context["seconds"] == pytest.approx(4)


async def test_a_rate_limiter_refuses_the_message_over_its_limit() -> None:
    transport = FakeTransport().set_rate_limiter_factory(_limited_to(2))

    assert await transport.send(_MESSAGE, _envelope()) is not None
    assert await transport.send(_MESSAGE, _envelope()) is not None
    with pytest.raises(RateLimitExceededError):
        _ = await transport.send(_MESSAGE, _envelope())

    assert len(transport.sent) == 2


async def test_a_refusal_of_the_rate_limiter_is_announced_as_a_failure() -> None:
    dispatcher, recorded = recording_dispatcher()
    transport = FakeTransport(dispatcher).set_rate_limiter_factory(_limited_to(1))
    _ = await transport.send(_MESSAGE, _envelope())
    recorded.clear()

    with pytest.raises(RateLimitExceededError) as caught:
        _ = await transport.send(_MESSAGE, _envelope())

    assert [type(event) for event in recorded] == [MessageEvent, FailedMessageEvent]
    failed = recorded[1]
    assert isinstance(failed, FailedMessageEvent)
    assert failed.get_error() is caught.value

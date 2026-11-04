"""The pace and the rate limiter set on a sendmail transport hold in both of its modes."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_clock import MockClock
from xtr_mime import Address, RawMessage
from xtr_rate_limiter import (
    InMemoryStorage,
    LimiterConfig,
    RateLimiterFactory,
    RateLimitExceededError,
)

from tests.support.sendmail_fakes import FakeSendmail, fake_command
from xtr_mailer import Envelope
from xtr_mailer.transport import SendmailTransport

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio

_MODES = pytest.mark.parametrize("flag", ["-bs", "-t"])


def _message() -> RawMessage:
    return RawMessage(b"Subject: x\r\n\r\nbody\r\n")


def _envelope() -> Envelope:
    return Envelope(Address("from@mail.com"), [Address("recipient@mail.com")])


def _limited_to(limit: int) -> RateLimiterFactory:
    return RateLimiterFactory(
        "mailer", LimiterConfig("fixed_window", limit=limit, interval="1 hour"), InMemoryStorage()
    )


@_MODES
async def test_sends_are_spaced_by_the_max_per_second(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, flag: str
) -> None:
    _ = FakeSendmail(monkeypatch, tmp_path)
    clock = MockClock()
    transport = SendmailTransport(fake_command(flag), clock=clock).set_max_per_second(1 / 5)
    start = clock.now().timestamp()

    elapsed: list[float] = []
    for _ in range(3):
        _ = await transport.send(_message(), _envelope())
        elapsed.append(clock.now().timestamp() - start)
    await transport.stop()

    assert elapsed == pytest.approx([0, 5, 10])


async def test_the_pace_holds_across_a_stopped_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _ = FakeSendmail(monkeypatch, tmp_path)
    clock = MockClock()
    transport = SendmailTransport(fake_command("-bs"), clock=clock).set_max_per_second(1 / 5)
    start = clock.now().timestamp()
    _ = await transport.send(_message(), _envelope())
    await transport.stop()

    _ = await transport.send(_message(), _envelope())
    await transport.stop()

    assert clock.now().timestamp() - start == pytest.approx(5)


@_MODES
async def test_the_rate_limiter_counts_each_email_once_and_refuses_the_one_over_the_limit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, flag: str
) -> None:
    _ = FakeSendmail(monkeypatch, tmp_path)
    transport = SendmailTransport(fake_command(flag)).set_rate_limiter_factory(_limited_to(2))
    sent = [await transport.send(_message(), _envelope()) for _ in range(2)]

    with pytest.raises(RateLimitExceededError):
        _ = await transport.send(_message(), _envelope())
    await transport.stop()

    assert None not in sent

# The checks exercise a backend's storage primitives directly, as another process would.
# pyright: reportPrivateUsage=false
"""The checks every run-control backend passes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Final

import anyio
import pytest
from pydantic_ai import CancellationToken
from pydantic_ai.exceptions import RunCancelled
from pydantic_ai.usage import RunUsage
from xtr_clock import MockClock

from xtr_ai.exception import RunInProgressError, UnknownRunError
from xtr_ai.run_state import RunState

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from contextlib import AbstractAsyncContextManager
    from datetime import datetime

    from xtr_ai.abstract_run_control import AbstractRunControl

__all__ = ["CONTRACT_POLL_INTERVAL", "RunControlContract"]

CONTRACT_POLL_INTERVAL: Final = 0.01
"""The ``cancel_poll_interval`` :meth:`RunControlContract.build` passes, so the checks run fast.

The other timings stay at their defaults: a heartbeat every 10 seconds, stale after 60.
"""

_WAIT: Final = 2.0


@pytest.mark.anyio
class RunControlContract(ABC):
    """Subclass in a backend's tests and implement :meth:`build`.

    ```python
    class TestMyRunControl(RunControlContract):
        @asynccontextmanager
        async def build(self, clock: MockClock) -> AsyncGenerator[AbstractRunControl]:
            yield MyRunControl(..., clock=clock, cancel_poll_interval=CONTRACT_POLL_INTERVAL)
    ```
    """

    @abstractmethod
    def build(self, clock: MockClock) -> AbstractAsyncContextManager[AbstractRunControl]:
        """Return an async context manager yielding an empty backend on ``clock``.

        Pass :data:`CONTRACT_POLL_INTERVAL` as its ``cancel_poll_interval``.
        """

    @pytest.fixture
    def anyio_backend(self) -> str:
        return "asyncio"

    @pytest.fixture
    def clock(self) -> MockClock:
        return MockClock("2026-01-01 10:00:00")

    @pytest.fixture
    async def control(self, clock: MockClock) -> AsyncGenerator[AbstractRunControl]:
        async with self.build(clock) as built:
            yield built

    async def test_a_started_run_is_running(
        self, control: AbstractRunControl, clock: MockClock
    ) -> None:
        _ = await control.start("r1", agent="chat", conversation_id="c1", metadata={"owner": "u1"})

        status = await control.get("r1")

        assert status is not None
        assert status.state is RunState.RUNNING
        assert status.agent == "chat"
        assert status.conversation_id == "c1"
        assert dict(status.metadata) == {"owner": "u1"}
        assert status.started_at == clock.now()
        assert not status.cancel_requested

    async def test_an_unknown_run_is_none(self, control: AbstractRunControl) -> None:
        assert await control.get("nope") is None

    async def test_a_conversation_has_one_top_level_run_at_a_time(
        self, control: AbstractRunControl
    ) -> None:
        _ = await control.start("r1", agent="chat", conversation_id="c1")

        with pytest.raises(RunInProgressError) as raised:
            _ = await control.start("r2", agent="chat", conversation_id="c1")

        assert raised.value.running_run_id == "r1"
        assert await control.get("r2") is None

    async def test_delegated_and_unrelated_runs_are_not_held_back(
        self, control: AbstractRunControl
    ) -> None:
        _ = await control.start("r1", agent="chat", conversation_id="c1")

        _ = await control.start("r2", agent="research", conversation_id="c1", parent_run_id="r1")
        _ = await control.start("r3", agent="chat", conversation_id="c2")
        _ = await control.start("r4", agent="chat")
        _ = await control.start("r5", agent="chat")

        for run_id in ("r2", "r3", "r4", "r5"):
            status = await control.get(run_id)
            assert status is not None
            assert status.is_running

    async def test_a_watched_block_that_returns_finishes_the_run(
        self, control: AbstractRunControl, clock: MockClock
    ) -> None:
        _ = await control.start("r1", agent="chat", conversation_id="c1")

        async with control.watch("r1", CancellationToken()) as watched:
            clock.sleep(5)
            watched.record_usage(RunUsage(requests=2, input_tokens=10, output_tokens=3))

        status = await control.get("r1")
        assert status is not None
        assert status.state is RunState.FINISHED
        assert status.usage is not None
        assert status.usage.requests == 2
        assert status.usage.output_tokens == 3
        assert status.finished_at == clock.now()

    async def test_a_finished_run_frees_its_conversation(self, control: AbstractRunControl) -> None:
        _ = await control.start("r1", agent="chat", conversation_id="c1")
        async with control.watch("r1", CancellationToken()):
            pass

        _ = await control.start("r2", agent="chat", conversation_id="c1")

    async def test_an_error_fails_the_run_and_propagates(self, control: AbstractRunControl) -> None:
        _ = await control.start("r1", agent="chat", conversation_id="c1")

        with pytest.raises(ValueError, match="boom"):
            async with control.watch("r1", CancellationToken()):
                raise ValueError("boom")

        status = await control.get("r1")
        assert status is not None
        assert status.state is RunState.FAILED

    async def test_a_cancelled_agent_run_cancels_the_run(self, control: AbstractRunControl) -> None:
        _ = await control.start("r1", agent="chat")

        with pytest.raises(RunCancelled):
            async with control.watch("r1", CancellationToken()):
                raise RunCancelled("cancelled")

        status = await control.get("r1")
        assert status is not None
        assert status.state is RunState.CANCELLED

    async def test_the_terminal_write_survives_the_callers_cancellation(
        self, control: AbstractRunControl
    ) -> None:
        _ = await control.start("r1", agent="chat")

        with anyio.CancelScope() as scope:
            async with control.watch("r1", CancellationToken()):
                scope.cancel()
                await anyio.sleep(_WAIT)

        status = await control.get("r1")
        assert status is not None
        assert status.state is RunState.CANCELLED

    async def test_a_cancellation_flagged_elsewhere_reaches_the_token(
        self, control: AbstractRunControl
    ) -> None:
        _ = await control.start("r1", agent="chat")
        token = CancellationToken()

        async with control.watch("r1", token):
            # What another process does: flag the stored run, without this process's token.
            assert await control._flag_cancel("r1")
            with anyio.fail_after(_WAIT):
                while not token.cancelled:
                    await anyio.sleep(0.005)

    async def test_a_cancellation_asked_here_reaches_the_token_at_once(
        self, control: AbstractRunControl
    ) -> None:
        _ = await control.start("r1", agent="chat")
        token = CancellationToken()

        async with control.watch("r1", token):
            assert await control.request_cancel("r1")
            assert token.cancelled

        status = await control.get("r1")
        assert status is not None
        assert status.cancel_requested

    async def test_asking_to_cancel_is_idempotent_and_says_whether_a_run_was_running(
        self, control: AbstractRunControl
    ) -> None:
        _ = await control.start("r1", agent="chat")

        assert await control.request_cancel("r1")
        assert await control.request_cancel("r1")
        assert not await control.request_cancel("nope")

        async with control.watch("r1", CancellationToken()):
            pass
        assert not await control.request_cancel("r1")

    async def test_the_first_terminal_state_wins(
        self, control: AbstractRunControl, clock: MockClock
    ) -> None:
        _ = await control.start("r1", agent="chat")
        async with control.watch("r1", CancellationToken()):
            pass

        assert not await control._finish("r1", RunState.FAILED, None, clock.now())

        status = await control.get("r1")
        assert status is not None
        assert status.state is RunState.FINISHED

    async def test_watching_a_run_never_started_is_refused(
        self, control: AbstractRunControl
    ) -> None:
        with pytest.raises(UnknownRunError):
            async with control.watch("nope", CancellationToken()):
                pass

    async def test_a_silent_run_loses_its_conversation(
        self, control: AbstractRunControl, clock: MockClock
    ) -> None:
        _ = await control.start("r1", agent="chat", conversation_id="c1")
        clock.sleep(61)

        _ = await control.start("r2", agent="chat", conversation_id="c1")

        crashed = await control.get("r1")
        assert crashed is not None
        assert crashed.state is RunState.FAILED

    async def test_a_watched_run_reports_itself_alive(
        self, control: AbstractRunControl, clock: MockClock
    ) -> None:
        _ = await control.start("r1", agent="chat", conversation_id="c1")

        async with control.watch("r1", CancellationToken()):
            clock.sleep(40)
            await self._wait_for_heartbeat(control, clock)
            clock.sleep(40)

            with pytest.raises(RunInProgressError):
                _ = await control.start("r2", agent="chat", conversation_id="c1")

    async def test_a_failed_poll_is_retried_and_the_watch_goes_on(
        self, control: AbstractRunControl, clock: MockClock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _ = await control.start("r1", agent="chat")
        polls: list[None] = []
        poll = control._poll

        async def flaky(run_id: str, heartbeat_at: datetime | None) -> bool:
            polls.append(None)
            if len(polls) == 1:
                raise OSError("the store is briefly unreachable")
            return await poll(run_id, heartbeat_at)

        monkeypatch.setattr(control, "_poll", flaky)
        token = CancellationToken()

        async with control.watch("r1", token):
            clock.sleep(15)
            await self._wait_for_heartbeat(control, clock)
            assert await control._flag_cancel("r1")
            with anyio.fail_after(_WAIT):
                while not token.cancelled:
                    await anyio.sleep(0.005)

        assert len(polls) >= 2

    async def test_a_run_taken_for_dead_is_stopped_where_it_runs(
        self, control: AbstractRunControl, clock: MockClock
    ) -> None:
        _ = await control.start("r1", agent="chat", conversation_id="c1")
        token = CancellationToken()

        async with control.watch("r1", token):
            # What another process does when it finds this run silent too long.
            assert await control._finish("r1", RunState.FAILED, None, clock.now())
            with anyio.fail_after(_WAIT):
                while not token.cancelled:
                    await anyio.sleep(0.005)

        status = await control.get("r1")
        assert status is not None
        assert status.state is RunState.FAILED

    async def _wait_for_heartbeat(self, control: AbstractRunControl, clock: MockClock) -> None:
        with anyio.fail_after(_WAIT):
            while True:
                status = await control.get("r1")
                if status is not None and status.heartbeat_at == clock.now():
                    return
                await anyio.sleep(0.005)

from __future__ import annotations

import pytest
from pydantic_ai import Agent
from pydantic_ai.exceptions import RunTimedOut
from pydantic_ai.models.test import TestModel
from xtr_clock import MockClock

from xtr_ai.run_clock import RunClock

pytestmark = pytest.mark.anyio


async def test_the_run_clock_is_the_injected_one() -> None:
    clock = MockClock("2026-01-01 10:00:00")

    run_clock = RunClock(clock).get_run_clock()

    assert run_clock() == clock.now()
    assert RunClock.get_serialization_name() is None


async def test_a_runs_deadline_is_measured_against_the_injected_clock() -> None:
    clock = MockClock("2026-01-01 10:00:00")
    inner = Agent(TestModel(custom_output_text="inner"))
    outer = Agent(TestModel(call_tools=["delegate"]), capabilities=[RunClock(clock)])
    raised: list[type[BaseException]] = []

    @outer.tool_plain
    async def delegate() -> str:
        # The outer run's clock moves past its deadline; a run started now inherits it.
        clock.sleep(60)
        try:
            result = await inner.run("go")
        except RunTimedOut as error:
            raised.append(type(error))
            raise
        return result.output

    _ = await outer.run("go", timeout=30)

    assert raised == [RunTimedOut]

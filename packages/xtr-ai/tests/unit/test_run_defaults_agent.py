from __future__ import annotations

import pytest
from pydantic_ai import Agent, RunContext
from pydantic_ai.agent import AbstractAgent
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import UsageLimits

from xtr_ai.run_defaults_agent import RunDefaultsAgent

pytestmark = pytest.mark.anyio


def _agent(usage_limits: UsageLimits | None = None) -> RunDefaultsAgent:
    wrapped = Agent(TestModel(call_tools="all"), name="chat")

    @wrapped.tool_plain
    def ping() -> str:
        return "pong"

    return RunDefaultsAgent(wrapped, usage_limits=usage_limits)


async def test_the_default_limits_apply_to_run() -> None:
    agent = _agent(usage_limits=UsageLimits(request_limit=1))

    with pytest.raises(UsageLimitExceeded):
        _ = await agent.run("go")


async def test_an_explicit_limit_wins_over_the_default() -> None:
    agent = _agent(usage_limits=UsageLimits(request_limit=1))

    result = await agent.run("go", usage_limits=UsageLimits(request_limit=5))

    assert result.usage.requests == 2


async def test_the_defaults_apply_to_run_stream() -> None:
    agent = _agent(usage_limits=UsageLimits(request_limit=1))

    with pytest.raises(UsageLimitExceeded):
        async with agent.run_stream("go") as stream:
            _ = await stream.get_output()


async def test_the_default_timeout_reaches_the_run() -> None:
    wrapped = Agent(TestModel(call_tools=["deadline"]))
    seen: list[object] = []

    @wrapped.tool
    def deadline(ctx: RunContext[object]) -> str:
        seen.append(ctx.deadline)
        return "ok"

    _ = await RunDefaultsAgent(wrapped, timeout=30.0).run("go")
    _ = await wrapped.run("go")

    assert seen[0] is not None
    assert seen[1] is None


def test_it_is_an_abstract_agent_not_an_agent() -> None:
    agent = _agent()

    assert isinstance(agent, AbstractAgent)
    assert not isinstance(agent, Agent)
    assert agent.name == "chat"

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from pydantic_ai import Agent
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import UsageLimits

from xtr_ai.agent_tool import agent_toolset

if TYPE_CHECKING:
    from pydantic_ai.agent import AbstractAgent

pytestmark = pytest.mark.anyio


async def test_the_tool_runs_the_other_agent_and_adds_its_usage() -> None:
    research = Agent(TestModel(custom_output_text="found it"), name="research")
    chat = Agent(
        TestModel(call_tools=["research"]),
        toolsets=[agent_toolset(research, name="research")],
    )

    result = await chat.run("look it up")

    assert "found it" in result.output
    assert result.usage.requests == 3  # two by chat, one by research


async def test_the_agent_is_looked_up_only_when_first_called() -> None:
    looked_up: list[str] = []
    research = Agent(TestModel(custom_output_text="ok"))

    async def lookup() -> AbstractAgent[Any, Any]:
        looked_up.append("research")
        return research

    toolset = agent_toolset(lookup, name="research", description="Research things.")
    chat = Agent(TestModel(call_tools=["research"]), toolsets=[toolset])

    assert looked_up == []
    _ = await chat.run("one")
    _ = await chat.run("two")

    assert looked_up == ["research"]
    assert toolset.tools["research"].description == "Research things."


async def test_a_delegated_run_uses_the_callers_usage_limits() -> None:
    # Without them the delegate runs under its own default limits, so a caller's
    # request_limit no longer bounds what one prompt can cost.
    asked: list[int] = []

    def looping(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        asked.append(1)
        return ModelResponse(parts=[ToolCallPart("again", {})])

    research = Agent(FunctionModel(looping), name="research")

    @research.tool_plain
    def again() -> str:
        return "keep going"

    chat = Agent(
        TestModel(call_tools=["research"]),
        toolsets=[agent_toolset(research, name="research")],
    )

    with pytest.raises(UsageLimitExceeded):
        _ = await chat.run("look it up", usage_limits=UsageLimits(request_limit=3))

    assert len(asked) == 2  # one by chat, two by research: three in all

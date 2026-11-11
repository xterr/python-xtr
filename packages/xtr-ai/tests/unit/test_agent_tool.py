from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

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

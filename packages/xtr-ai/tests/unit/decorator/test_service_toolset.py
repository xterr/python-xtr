from __future__ import annotations

import pytest
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.test import TestModel

from xtr_ai.decorator import as_tool, service_toolset

pytestmark = pytest.mark.anyio


class Counter:
    def __init__(self) -> None:
        self.calls: list[str] = []

    @as_tool(agents=("chat",))
    def bump(self, label: str) -> str:
        """Count one call."""
        self.calls.append(label)
        return f"counted {label}"

    @as_tool(agents=("chat",), name="whoami")
    async def identity(self, ctx: RunContext[str]) -> str:
        return ctx.deps

    @as_tool(agents=("ops",))
    def reset(self) -> None:
        self.calls.clear()


async def test_only_the_tools_of_the_agent_are_kept() -> None:
    toolset = service_toolset(Counter(), "chat")

    assert sorted(toolset.tools) == ["bump", "whoami"]
    assert sorted(service_toolset(Counter()).tools) == ["bump", "reset", "whoami"]


async def test_an_agent_calls_the_bound_method() -> None:
    counter = Counter()
    agent = Agent(
        TestModel(call_tools=["bump", "whoami"]),
        deps_type=str,
        toolsets=[service_toolset(counter, "chat")],
    )

    result = await agent.run("go", deps="alice")

    assert counter.calls == ["a"]
    assert "alice" in result.output

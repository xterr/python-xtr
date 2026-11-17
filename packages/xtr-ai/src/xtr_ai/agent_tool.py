"""Calling one agent from another, as a tool."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from pydantic_ai import (
    RunContext,  # noqa: TC002 — pydantic-ai reads a tool's annotations at runtime
)
from pydantic_ai.agent import AbstractAgent
from pydantic_ai.toolsets import FunctionToolset

__all__ = ["agent_toolset"]

AgentSource = AbstractAgent[Any, Any] | Callable[[], Awaitable[AbstractAgent[Any, Any]]]
"""An agent, or what returns it when the tool is first called."""


def agent_toolset(
    agent: AgentSource,
    *,
    name: str,
    description: str | None = None,
) -> FunctionToolset[Any]:
    """Return a toolset of one tool, ``name``, that runs ``agent`` on a prompt.

    The delegated run receives the calling run's dependencies, adds its usage
    to the calling run's and runs under the calling run's usage limits, so one
    prompt's limits bound everything it sets off — the delegated agent's own
    limits do not apply. It also inherits the
    caller's deadline. Pass a function returning the agent to build it only
    when the tool is first called.

    Args:
        agent: The agent to delegate to, or what returns it.
        name: The tool's name.
        description: What the calling model reads about the tool.
    """
    resolved: list[AbstractAgent[Any, Any]] = []

    async def delegate(ctx: RunContext[Any], prompt: str) -> Any:
        if not resolved:
            resolved.append(agent if isinstance(agent, AbstractAgent) else await agent())
        result = await resolved[0].run(
            prompt, deps=ctx.deps, usage=ctx.usage, usage_limits=ctx.usage_limits
        )
        return result.output

    toolset: FunctionToolset[Any] = FunctionToolset()
    _ = toolset.add_function(
        delegate,
        takes_ctx=True,
        name=name,
        description=description or f'Ask the "{name}" agent; give it the whole request.',
    )
    return toolset

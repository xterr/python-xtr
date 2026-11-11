"""Running a configured agent on a model the test scripts."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Protocol, TypeVar

from pydantic_ai.agent import AbstractAgent

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Hashable

    from pydantic_ai.models import Model

__all__ = ["override_agent_model"]

_T = TypeVar("_T")


class _Container(Protocol):
    async def get(self, service: type[_T], qualifier: Hashable | None = None, /) -> _T: ...


@asynccontextmanager
async def override_agent_model(
    container: _Container, name: str, model: Model
) -> AsyncGenerator[AbstractAgent[Any, Any]]:
    """Run the agent ``name`` on ``model`` inside the block, in this task only.

    pydantic-ai's ``agent.override`` is scoped to the running context, so
    concurrent tests do not see each other's models::

        async with override_agent_model(booted.container, "chat", FunctionModel(reply)) as agent:
            result = await agent.run("hi")
    """
    agent = await container.get(AbstractAgent, name)
    with agent.override(model=model):
        yield agent

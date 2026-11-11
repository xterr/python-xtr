"""The toolset a service's declared methods make."""

from __future__ import annotations

from typing import Any

from pydantic_ai.toolsets import FunctionToolset

from .tools_declared_on import tools_declared_on

__all__ = ["service_toolset"]


def service_toolset(service: object, agent: str | None = None) -> FunctionToolset[Any]:
    """Return a toolset of ``service``'s ``@as_tool`` methods, bound to it.

    Args:
        service: The instance whose methods are called.
        agent: Keep only the tools declared for this agent; every tool when ``None``.
    """
    toolset: FunctionToolset[Any] = FunctionToolset()
    for declaration in tools_declared_on(type(service)):
        if agent is not None and agent not in declaration.agents:
            continue
        _ = toolset.add_function(
            getattr(service, declaration.method),
            name=declaration.name,
            description=declaration.description,
        )
    return toolset

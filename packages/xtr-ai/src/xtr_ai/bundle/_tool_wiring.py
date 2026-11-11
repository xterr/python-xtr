"""Collecting ``@as_tool`` methods into toolsets the container builds."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Final

from pydantic_ai.toolsets import AbstractToolset
from xtr_dependency_injection import ServiceConfigurator, named_factory, qualified_name

from xtr_ai.decorator import service_toolset, tools_declared_on

__all__ = ["TOOL_TAG", "classes_declaring_tools", "tools_registrar"]

TOOL_TAG: Final = "ai.tool"
"""The tag on the toolset built from a class's ``@as_tool`` methods for one agent."""


def classes_declaring_tools(candidate: object) -> tuple[type, ...]:
    """The autoconfiguration reader: the candidate itself when it is a class declaring tools."""
    if isinstance(candidate, type) and tuple(tools_declared_on(candidate)):
        return (candidate,)
    return ()


def tools_registrar(
    declaring_classes: set[type],
) -> Callable[[object, type, ServiceConfigurator], None]:
    """The autoconfiguration callback: one toolset per agent a class's tools are declared for.

    The class itself is remembered in ``declaring_classes``, for the bundle to
    register it afterwards unless the application registered it already.
    """

    def register_tools(candidate: object, declaring: type, services: ServiceConfigurator) -> None:
        del candidate
        declaring_classes.add(declaring)
        agents = sorted({agent for tool in tools_declared_on(declaring) for agent in tool.agents})
        for agent in agents:
            _ = services.set(
                _toolset_factory(declaring, agent), qualifier=tool_qualifier(declaring, agent)
            ).add_tag(TOOL_TAG, agent=agent, service=qualified_name(declaring))

    return register_tools


def tool_qualifier(declaring: type, agent: str) -> str:
    """The qualifier of the toolset ``declaring``'s tools make for ``agent``."""
    return f"ai_tools_{agent}_{qualified_name(declaring)}"


def _toolset_factory(declaring: type, agent: str) -> Any:
    def toolset(service: Any) -> AbstractToolset[Any]:
        return service_toolset(service, agent)

    toolset.__annotations__ = {"service": declaring, "return": AbstractToolset}
    return named_factory(toolset, f"ai_tools_{agent}_{declaring.__name__}")

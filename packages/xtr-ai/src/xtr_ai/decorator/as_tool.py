"""Marking a service method as a tool."""

from __future__ import annotations

from collections.abc import Callable
from typing import Final, TypeVar

from xtr_ai.exception import InvalidConfigurationError

from .tool_declaration import ToolDeclaration

__all__ = ["TOOL_ATTRIBUTE", "as_tool"]

TOOL_ATTRIBUTE: Final = "__xtr_ai_tool__"
"""The attribute ``@as_tool`` sets on the method it marks."""

_F = TypeVar("_F", bound=Callable[..., object])


def as_tool(
    *,
    agents: tuple[str, ...],
    name: str | None = None,
    description: str | None = None,
) -> Callable[[_F], _F]:
    """Declare a method of a service a tool of the agents named.

    The method is called on the service the container builds, so the service's
    own dependencies are injected as usual. Its first parameter may be a
    pydantic-ai ``RunContext``; the rest are the tool's arguments, described by
    their annotations and the docstring::

        class Weather:
            def __init__(self, client: Injected[WeatherClient]) -> None:
                self._client = client

            @as_tool(agents=("chat",))
            async def forecast(self, city: str) -> str:
                \"\"\"Tomorrow's forecast for a city.\"\"\"
                return await self._client.forecast(city)

    Without the container, :func:`~xtr_ai.decorator.service_toolset` builds
    the same toolset from an instance.

    Args:
        agents: The agents that get the tool. At least one.
        name: The tool's name; the method's name when left out.
        description: The tool's description; the docstring when left out.

    Raises:
        InvalidConfigurationError: When no agent is named, or the decorated
            object is a module-level function rather than a method.
    """
    if not agents:
        raise InvalidConfigurationError("@as_tool needs at least one agent in agents=.")

    def mark(method: _F) -> _F:
        qualname: str = getattr(method, "__qualname__", "")
        owner, _, method_name = qualname.rpartition(".")
        if not owner or owner.endswith("<locals>"):
            raise InvalidConfigurationError(
                f"@as_tool marks methods of a service class; {qualname or method!r} is a function."
            )
        declaration = ToolDeclaration(
            method=method_name,
            agents=tuple(agents),
            name=name,
            description=description,
        )
        setattr(method, TOOL_ATTRIBUTE, declaration)
        return method

    return mark

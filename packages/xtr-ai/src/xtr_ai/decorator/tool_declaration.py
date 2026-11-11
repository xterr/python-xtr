"""What ``@as_tool`` records on a method."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

__all__ = ["ToolDeclaration"]


@final
@dataclass(frozen=True, slots=True)
class ToolDeclaration:
    """A method declared a tool, for the agents named.

    Attributes:
        method: The method's attribute name on its class.
        agents: The agents the tool is given to.
        name: The tool's name; the method's name when ``None``.
        description: The tool's description; the method's docstring when ``None``.
    """

    method: str
    agents: tuple[str, ...]
    name: str | None = None
    description: str | None = None

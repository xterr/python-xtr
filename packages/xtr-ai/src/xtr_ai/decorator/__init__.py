"""Declaring a service's methods as tools an agent can call."""

from __future__ import annotations

from .as_tool import TOOL_ATTRIBUTE, as_tool
from .service_toolset import service_toolset
from .tool_declaration import ToolDeclaration
from .tools_declared_on import tools_declared_on

__all__ = [
    "TOOL_ATTRIBUTE",
    "ToolDeclaration",
    "as_tool",
    "service_toolset",
    "tools_declared_on",
]

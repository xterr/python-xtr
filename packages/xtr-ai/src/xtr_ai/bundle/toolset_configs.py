"""The toolsets an agent is given besides its ``@as_tool`` methods."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeAlias, final

from pydantic_ai.toolsets import AbstractToolset

__all__ = ["AgentToolRef", "ToolsetEntry", "ToolsetRef"]


@final
@dataclass(frozen=True, slots=True)
class ToolsetRef:
    """A toolset the container builds: a pydantic-ai ``AbstractToolset`` subclass, with injection.

    The class is registered as a singleton unless the application registers it
    itself.
    """

    service: type[AbstractToolset[Any]]


@final
@dataclass(frozen=True, slots=True)
class AgentToolRef:
    """Another configured agent, called as a tool.

    Attributes:
        agent: The agent to call.
        name: The tool's name; the agent's name when left out.
        description: What the calling model reads about the tool.
    """

    agent: str
    name: str | None = None
    description: str | None = None


ToolsetEntry: TypeAlias = ToolsetRef | AgentToolRef
"""What an agent's ``toolsets`` holds."""

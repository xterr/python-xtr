"""One agent's configuration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import NoneType
from typing import Any, Literal, TypeAlias, final

from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.usage import UsageLimits

from xtr_ai.exception import InvalidConfigurationError

from ._placeholder import is_literal
from .model_ref import ModelRef
from .toolset_configs import ToolsetEntry

__all__ = ["AgentConfig", "CapabilityEntry"]

CapabilityEntry: TypeAlias = (
    str | Mapping[str, Any] | AbstractCapability[Any] | type[AbstractCapability[Any]]
)
"""A capability: pydantic-ai's declarative form (``"Thinking"``, ``{"Thinking": {...}}``), a
capability itself (``Thinking(effort="low")``), or a capability class the container builds, with
injection."""


@final
@dataclass(frozen=True, slots=True)
class AgentConfig:
    """An agent: its model, its instructions, its capabilities and tools, and run defaults.

    Attributes:
        platform: The platform its model runs on; may be ``env("…")`` to choose
            per environment.
        model: The model's name on that platform; may be ``env("…")`` too.
        fallbacks: Models tried in order when the model fails.
        instructions: The instructions, inline.
        instructions_file: A file holding them instead, read when the agent is
            first built. ``%kernel.project_dir%`` may start the path.
        model_settings: pydantic-ai model settings for every run.
        retries: Tool and output retry budget.
        end_strategy: pydantic-ai's end strategy.
        tool_timeout: Default timeout of a tool call, in seconds.
        metadata: Stored with every run.
        deps_type: The type of the dependencies a run is given.
        output_type: What a run returns.
        capabilities: Capabilities: declarative, built already, or classes the container builds.
        toolsets: Toolsets the container builds, and agents called as tools.
        usage_limits: Default usage limits of a run; a call passing its own wins.
        timeout: Default timeout of a run, in seconds; a call passing its own wins.
    """

    platform: str
    model: str
    fallbacks: tuple[ModelRef, ...] = ()
    instructions: str | None = None
    instructions_file: str | None = None
    model_settings: Mapping[str, Any] = field(default_factory=dict[str, Any])
    retries: int | None = None
    end_strategy: Literal["early", "graceful", "exhaustive"] = "graceful"
    tool_timeout: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict[str, Any])
    deps_type: type[Any] = NoneType
    output_type: Any = str
    capabilities: tuple[CapabilityEntry, ...] = ()
    toolsets: tuple[ToolsetEntry, ...] = ()
    usage_limits: UsageLimits | None = None
    timeout: float | None = None

    def __post_init__(self) -> None:
        """Refuse what can be refused before the environment is read.

        Raises:
            InvalidConfigurationError: When both kinds of instructions are
                given, or a literal platform, model or timeout is unusable.
        """
        if self.instructions is not None and self.instructions_file is not None:
            raise InvalidConfigurationError(
                "An agent takes instructions or instructions_file, not both."
            )
        if is_literal(self.platform) and not self.platform:
            raise InvalidConfigurationError("An agent needs a platform.")
        if is_literal(self.model) and not self.model:
            raise InvalidConfigurationError("An agent needs a model.")
        if self.timeout is not None and is_literal(self.timeout) and self.timeout <= 0:
            raise InvalidConfigurationError("An agent's timeout must be positive.")

    @property
    def model_id(self) -> str:
        """The id the agent's model is resolved by: ``<platform>:<model>``."""
        return f"{self.platform}:{self.model}"

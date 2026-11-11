"""Turning an agent's configuration into a pydantic-ai agent."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import anyio
from pydantic_ai import Agent
from pydantic_ai.capabilities import AbstractCapability, ModelFallback, ResolveModelId

from xtr_ai.agent_tool import agent_toolset
from xtr_ai.exception import PlatformUnavailableError
from xtr_ai.run_clock import RunClock
from xtr_ai.run_defaults_agent import RunDefaultsAgent
from xtr_ai.run_logging import RunLogging

from .toolset_configs import AgentToolRef

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from pydantic_ai.agent import AbstractAgent
    from pydantic_ai.toolsets import AbstractToolset
    from xtr_clock import ClockInterface
    from xtr_logging_contracts import LoggerInterface

    from xtr_ai.platform_registry_interface import PlatformRegistryInterface

    from .agent_config import AgentConfig

__all__ = ["build_agent"]


async def build_agent(  # noqa: PLR0913 — an agent's configuration and every service it is built from
    name: str,
    config: AgentConfig,
    *,
    registry: PlatformRegistryInterface,
    capabilities: Sequence[AbstractCapability[Any]],
    toolsets: Sequence[AbstractToolset[Any]],
    agent_lookup: Callable[[str], Awaitable[AbstractAgent[Any, Any]]],
    clock: ClockInterface | None,
    logger: LoggerInterface | None,
) -> AbstractAgent[Any, Any]:
    """Build the agent ``name`` from ``config`` with pydantic-ai's ``Agent.from_spec``.

    The declarative part of the configuration — model, instructions, settings,
    the capabilities written as names or mappings — goes through pydantic-ai's
    own loader; types and built objects are passed beside it. Every model id is
    resolved through ``registry``; no platform is built here.

    Raises:
        PlatformUnavailableError: When the agent or a fallback names a
            platform that is not configured — possible only when it came from
            the environment, as literal ones are checked while building.
    """
    for platform in (config.platform, *(fallback.platform for fallback in config.fallbacks)):
        if not registry.has(platform):
            configured = ", ".join(f'"{known}"' for known in registry.names) or "none"
            raise PlatformUnavailableError(
                platform,
                f'the "{name}" agent names it, but no platform of that name is configured '
                f"(configured: {configured})",
            )
    instructions = config.instructions
    if config.instructions_file is not None:
        instructions = await anyio.Path(config.instructions_file).read_text(encoding="utf-8")
    # Instructions go beside the declarative part, not in it: pydantic-ai reads instructions
    # written there as templates, and a prompt quoting ``{{ ... }}`` would fail to build.
    definition: dict[str, Any] = {
        "model": config.model_id,
        "name": name,
        "model_settings": dict(config.model_settings) or None,
        "retries": config.retries,
        "end_strategy": config.end_strategy,
        "tool_timeout": config.tool_timeout,
        "metadata": dict(config.metadata) or None,
        "capabilities": [
            entry
            for entry in config.capabilities
            if not isinstance(entry, (type, AbstractCapability))
        ],
    }
    built_capabilities: list[AbstractCapability[Any]] = [ResolveModelId(registry.resolve)]
    if config.fallbacks:
        built_capabilities.append(
            ModelFallback(*(fallback.model_id for fallback in config.fallbacks))
        )
    built_capabilities.extend(capabilities)
    built_capabilities.extend(
        entry for entry in config.capabilities if isinstance(entry, AbstractCapability)
    )
    if clock is not None:
        built_capabilities.append(RunClock(clock))
    if logger is not None:
        built_capabilities.append(RunLogging(logger, registry))
    all_toolsets: list[AbstractToolset[Any]] = [
        *toolsets,
        *(
            _delegate(entry, agent_lookup)
            for entry in config.toolsets
            if isinstance(entry, AgentToolRef)
        ),
    ]
    agent: Agent[Any, Any] = Agent.from_spec(
        definition,
        instructions=instructions,
        deps_type=config.deps_type,
        output_type=config.output_type,
        toolsets=all_toolsets or None,
        capabilities=built_capabilities,
    )
    if config.usage_limits is None and config.timeout is None:
        return agent
    return RunDefaultsAgent(agent, usage_limits=config.usage_limits, timeout=config.timeout)


def _delegate(
    reference: AgentToolRef,
    agent_lookup: Callable[[str], Awaitable[AbstractAgent[Any, Any]]],
) -> AbstractToolset[Any]:
    async def target() -> AbstractAgent[Any, Any]:
        return await agent_lookup(reference.agent)

    return agent_toolset(
        target,
        name=reference.name or reference.agent,
        description=reference.description,
    )

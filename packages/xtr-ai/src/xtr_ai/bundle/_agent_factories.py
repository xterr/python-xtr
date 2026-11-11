"""The factory of each configured agent."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated, Any, Final

from pydantic_ai.agent import AbstractAgent
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.toolsets import AbstractToolset
from xtr_clock import ClockInterface
from xtr_dependency_injection import ServiceLocator, Target, named_factory
from xtr_logging_contracts import LoggerInterface

from xtr_ai.platform_registry_interface import PlatformRegistryInterface

from ._agent_builder import build_agent
from .agent_config import AgentConfig

__all__ = ["AI_CHANNEL", "agent_factory"]

AI_CHANNEL: Final = "ai"
"""The log channel runs are logged on, when the logging bundle is active."""


def agent_factory(name: str) -> Callable[..., Awaitable[AbstractAgent[Any, Any]]]:
    """Build the factory of the agent ``name``.

    Its configuration is the definition's own argument, so the ``env()``
    placeholders in it are read when this agent is first built. The bundle
    sets ``clock`` and ``logger`` to ``None`` when their bundles are not
    active, and hands over the qualifiers of the capabilities and toolsets
    the container builds for it.
    """

    async def agent(  # noqa: PLR0913 — every service an agent is built from
        *,
        registry: PlatformRegistryInterface,
        capabilities: ServiceLocator[AbstractCapability[Any]],
        toolsets: ServiceLocator[AbstractToolset[Any]],
        agents: ServiceLocator[AbstractAgent[Any, Any]],
        agent_config: AgentConfig,
        capability_qualifiers: tuple[str, ...] = (),
        toolset_qualifiers: tuple[str, ...] = (),
        clock: ClockInterface | None = None,
        logger: LoggerInterface | None = None,
    ) -> AbstractAgent[Any, Any]:
        return await build_agent(
            name,
            agent_config,
            registry=registry,
            capabilities=[await capabilities.get(key) for key in capability_qualifiers],
            toolsets=[await toolsets.get(key) for key in toolset_qualifiers],
            agent_lookup=agents.get,
            clock=clock,
            logger=logger,
        )

    # The container reads these to inject: the collections and the agent's own key are the
    # bare classes an application names, not the parameterised forms the code is typed with.
    agent.__annotations__ = {
        "registry": PlatformRegistryInterface,
        "capabilities": ServiceLocator[AbstractCapability],
        "toolsets": ServiceLocator[AbstractToolset],
        "agents": ServiceLocator[AbstractAgent],
        "agent_config": AgentConfig,
        "capability_qualifiers": tuple[str, ...],
        "toolset_qualifiers": tuple[str, ...],
        "clock": ClockInterface,
        "logger": Annotated[LoggerInterface, Target(AI_CHANNEL)],
        "return": AbstractAgent,
    }
    return named_factory(agent, f"ai_agent_{name}")

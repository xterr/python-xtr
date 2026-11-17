"""A toolset per scope under ``AbstractToolset``, which no agent references."""

from __future__ import annotations

from typing import Any

from pydantic_ai.toolsets import AbstractToolset, FunctionToolset
from xtr_dependency_injection import as_service, configure

from xtr_ai.bundle import AgentConfig, AiConfig, PlatformConfig


@as_service(lifetime="scoped", qualifier="per_request")
def per_request_toolset() -> AbstractToolset[Any]:
    """A toolset the application builds per request, for its own use."""
    return FunctionToolset()


@configure
def ai() -> AiConfig:
    """One agent, referencing no toolset."""
    return AiConfig(
        platforms={"offline": PlatformConfig(provider="test")},
        agents={"chat": AgentConfig(platform="offline", model="m")},
    )

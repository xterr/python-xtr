"""An agent built from a capability registered per scope."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic_ai.capabilities import AbstractCapability
from typing_extensions import override
from xtr_dependency_injection import as_service, configure

from xtr_ai.bundle import AgentConfig, AiConfig, PlatformConfig


@as_service(lifetime="scoped")
@dataclass
class PerRequest(AbstractCapability[Any]):
    @classmethod
    @override
    def get_serialization_name(cls) -> str | None:
        return None


@configure
def ai() -> AiConfig:
    return AiConfig(
        platforms={"offline": PlatformConfig(provider="test")},
        agents={"chat": AgentConfig(platform="offline", model="m", capabilities=(PerRequest,))},
    )

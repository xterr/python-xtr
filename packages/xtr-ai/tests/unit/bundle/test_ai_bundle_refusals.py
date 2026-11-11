from __future__ import annotations

import pytest
from xtr_dependency_injection import Kernel

from xtr_ai.bundle import AgentConfig, AgentToolRef, AiConfig, ModelRef, PlatformConfig
from xtr_ai.bundle._references import check_references
from xtr_ai.exception import InvalidConfigurationError

pytestmark = pytest.mark.anyio

_PLATFORMS = {"p": PlatformConfig(provider="test")}


def test_an_agent_naming_an_unknown_platform_is_refused() -> None:
    config = AiConfig(platforms=_PLATFORMS, agents={"a": AgentConfig(platform="q", model="m")})

    with pytest.raises(InvalidConfigurationError, match='"a" agent names the "q" platform'):
        check_references(config)


def test_a_fallback_naming_an_unknown_platform_is_refused() -> None:
    agent = AgentConfig(platform="p", model="m", fallbacks=(ModelRef("q", "m"),))

    with pytest.raises(InvalidConfigurationError, match='"q" platform'):
        check_references(AiConfig(platforms=_PLATFORMS, agents={"a": agent}))


def test_calling_an_unknown_agent_is_refused() -> None:
    agent = AgentConfig(platform="p", model="m", toolsets=(AgentToolRef("ghost"),))

    with pytest.raises(InvalidConfigurationError, match='calls the "ghost" agent'):
        check_references(AiConfig(platforms=_PLATFORMS, agents={"a": agent}))


def test_agents_calling_each_other_in_a_cycle_are_refused() -> None:
    agents = {
        "a": AgentConfig(platform="p", model="m", toolsets=(AgentToolRef("b"),)),
        "b": AgentConfig(platform="p", model="m", toolsets=(AgentToolRef("a"),)),
    }

    with pytest.raises(InvalidConfigurationError, match="cycle: a -> b -> a"):
        check_references(AiConfig(platforms=_PLATFORMS, agents=agents))


async def test_a_tool_for_an_unknown_agent_is_refused() -> None:
    with pytest.raises(InvalidConfigurationError, match='"ghost" agent, which is not configured'):
        _ = await Kernel("tests.fixtures.app_ai_stray_tool", env="test").boot()


async def test_a_capability_that_is_not_a_singleton_is_refused() -> None:
    with pytest.raises(InvalidConfigurationError, match="registered scoped"):
        _ = await Kernel("tests.fixtures.app_ai_scoped", env="test").boot()

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from pydantic_ai.capabilities import Thinking
from pydantic_ai.exceptions import ModelHTTPError

from xtr_ai.bundle import AgentConfig, ModelRef
from xtr_ai.bundle._agent_builder import build_agent
from xtr_ai.exception import PlatformUnavailableError
from xtr_ai.platform import Platform
from xtr_ai.platform_registry import PlatformRegistry

if TYPE_CHECKING:
    from pydantic_ai.agent import AbstractAgent
    from pydantic_ai.messages import ModelMessage, ModelResponse
    from pydantic_ai.models.function import AgentInfo

pytestmark = pytest.mark.anyio


def _unavailable(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    del messages, info
    raise ModelHTTPError(status_code=503, model_name="primary")


async def _never(name: str) -> AbstractAgent[Any, Any]:
    raise AssertionError(name)


async def _build(config: AgentConfig, registry: PlatformRegistry) -> AbstractAgent[Any, Any]:
    return await build_agent(
        "chat",
        config,
        registry=registry,
        capabilities=(),
        toolsets=(),
        agent_lookup=_never,
        clock=None,
        logger=None,
    )


async def test_a_failing_model_falls_back_to_another_platform() -> None:
    registry = PlatformRegistry.of(
        Platform("primary", "function", options={"function": _unavailable}),
        Platform("backup", "test", options={"custom_output_text": "from the backup"}),
    )
    config = AgentConfig(platform="primary", model="m", fallbacks=(ModelRef("backup", "b"),))

    result = await (await _build(config, registry)).run("hi")

    assert result.output == "from the backup"


async def test_a_fallback_on_an_unknown_platform_is_unavailable() -> None:
    registry = PlatformRegistry.of(Platform("primary", "test"))
    config = AgentConfig(platform="primary", model="m", fallbacks=(ModelRef("gone", "b"),))

    with pytest.raises(PlatformUnavailableError, match='"gone" platform'):
        _ = await _build(config, registry)


async def test_instructions_quoting_template_braces_are_sent_as_written() -> None:
    registry = PlatformRegistry.of(Platform("p", "test"))
    config = AgentConfig(platform="p", model="m", instructions="Reply like {{ name }}.")

    result = await (await _build(config, registry)).run("hi")

    request = result.all_messages()[0]
    assert getattr(request, "instructions", None) == "Reply like {{ name }}."


async def test_a_capability_given_built_is_used_as_given() -> None:
    registry = PlatformRegistry.of(Platform("p", "test"))
    thinking = Thinking(effort="low")
    config = AgentConfig(platform="p", model="m", capabilities=(thinking, "WebSearch"))

    agent = await _build(config, registry)

    kinds = {type(capability).__name__ for capability in agent.root_capability.capabilities}
    assert {"Thinking", "WebSearch"} <= kinds

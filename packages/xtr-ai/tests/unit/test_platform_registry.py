from __future__ import annotations

import pytest
from pydantic_ai import Agent
from pydantic_ai.capabilities import ResolveModelId
from pydantic_ai.models.test import TestModel

from xtr_ai.exception import PlatformUnavailableError
from xtr_ai.platform import Platform
from xtr_ai.platform_registry import PlatformRegistry

pytestmark = pytest.mark.anyio


async def test_a_model_id_resolves_through_its_platform() -> None:
    registry = PlatformRegistry.of(Platform("local", "test"))

    model = await registry.model("local:llama")

    assert isinstance(model, TestModel)
    assert model.model_name == "llama"


async def test_an_id_naming_no_platform_is_left_to_pydantic_ai() -> None:
    registry = PlatformRegistry.of(Platform("local", "test"))

    assert await registry.model("openai:gpt-5") is None
    assert await registry.model("test") is None


async def test_a_platform_is_looked_up_once_and_only_when_needed() -> None:
    asked: list[str] = []

    async def lookup(name: str) -> Platform:
        asked.append(name)
        return Platform(name, "test")

    registry = PlatformRegistry(("a", "b"), lookup)
    _ = await registry.model("a:x")
    _ = await registry.model("a:y")

    assert asked == ["a"]
    assert registry.names == ("a", "b")
    assert registry.has("b")
    assert not registry.has("c")


async def test_an_unknown_platform_names_the_configured_ones() -> None:
    registry = PlatformRegistry.of(Platform("a", "test"))

    with pytest.raises(PlatformUnavailableError, match='configured: "a"'):
        _ = await registry.get("b")


async def test_an_empty_registry_says_none_is_configured() -> None:
    with pytest.raises(PlatformUnavailableError, match="configured: none"):
        _ = await PlatformRegistry.of().get("b")


async def test_an_agent_runs_on_a_platform_through_the_resolver() -> None:
    registry = PlatformRegistry.of(Platform("local", "test", options={"custom_output_text": "ok"}))
    agent = Agent("local:any", capabilities=[ResolveModelId(registry.resolve)])

    result = await agent.run("hello")

    assert result.output == "ok"


async def test_a_run_switches_platform_with_its_model_argument() -> None:
    registry = PlatformRegistry.of(
        Platform("a", "test", options={"custom_output_text": "from a"}),
        Platform("b", "test", options={"custom_output_text": "from b"}),
    )
    agent = Agent("a:m", capabilities=[ResolveModelId(registry.resolve)])

    result = await agent.run("hello", model="b:m")

    assert result.output == "from b"


async def test_closing_the_registry_closes_what_it_built() -> None:
    _ = pytest.importorskip("openai")
    platform = Platform("a", "openai", api_key="sk")
    registry = PlatformRegistry.of(platform)
    _ = await registry.get("a")
    provider = platform.provider_instance()

    await registry.aclose()

    own_client = provider._own_http_client
    assert own_client is None or own_client.is_closed

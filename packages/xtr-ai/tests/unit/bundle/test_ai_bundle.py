from __future__ import annotations

import subprocess
import sys
from collections.abc import Hashable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from pydantic_ai import CancellationToken
from pydantic_ai.agent import AbstractAgent
from pydantic_ai.conversation_store import ConversationStore, InMemoryConversationStore
from xtr_dependency_injection import ContainerBuilder, Kernel, bundle_active
from xtr_dependency_injection.testing import assert_zero_config
from xtr_logging_contracts import LoggerInterface

from xtr_ai import (
    PlatformInterface,
    PlatformRegistry,
    PlatformRegistryInterface,
    PlatformUnavailableError,
    RunClock,
    RunDefaultsAgent,
    RunLogging,
    RunState,
)
from xtr_ai.bundle import AI_CHANNEL, AiBundle
from xtr_ai.run_control_interface import RunControlInterface

if TYPE_CHECKING:
    from xtr_dependency_injection import BootedKernel

pytestmark = pytest.mark.anyio

APP = "tests.fixtures.app_ai"


def _kernel(**environ: str) -> Kernel:
    return Kernel(APP, env="test", environ=environ)


async def _agent(booted: BootedKernel, name: str) -> AbstractAgent[Any, Any]:
    return await booted.container.get(AbstractAgent, name)


async def test_zero_config_boots_and_shuts_down() -> None:
    await assert_zero_config(AiBundle)


async def test_an_agent_is_injected_by_name_and_all_of_them_together() -> None:
    async with await _kernel().boot() as booted:
        chat = await _agent(booted, "chat")
        everything = await booted.container.get(Mapping[Hashable, AbstractAgent])

        assert chat.name == "chat"
        assert sorted(str(key) for key in everything) == ["chat", "research"]
        assert everything["chat"] is chat


async def test_run_defaults_wrap_only_the_agents_that_set_them() -> None:
    async with await _kernel().boot() as booted:
        assert isinstance(await _agent(booted, "chat"), RunDefaultsAgent)
        assert not isinstance(await _agent(booted, "research"), RunDefaultsAgent)


async def test_instructions_are_read_from_a_file_under_the_project() -> None:
    async with await _kernel().boot() as booted:
        research = await _agent(booted, "research")
        async with research.iter("hi") as run:
            async for _ in run:
                pass

    assert run.result is not None
    request = run.result.all_messages()[0]
    assert getattr(request, "instructions", None) == "Research carefully."


async def test_platform_settings_reach_the_model_beneath_the_agents() -> None:
    async with await _kernel().boot() as booted:
        registry = await booted.container.get(PlatformRegistry)
        model = await registry.model("offline:m")

    assert model is not None
    assert model.settings == {"temperature": 0.3}


async def test_platforms_and_the_registry_are_injected_by_their_interfaces() -> None:
    async with await _kernel().boot() as booted:
        platform = await booted.container.get(PlatformInterface, "offline")
        registry = await booted.container.get(PlatformRegistryInterface)
        concrete = await booted.container.get(PlatformRegistry)
        same = await registry.get("offline")

    assert platform.provider == "test"
    assert registry is concrete
    assert same is platform


async def test_a_run_uses_tools_capabilities_and_another_agent() -> None:
    async with await _kernel().boot() as booted:
        result = await (await _agent(booted, "chat")).run("who is ada?")

    assert "Ada Lovelace" in result.output
    assert "offline answer" in result.output
    assert "Greet Ada Lovelace." in result.output
    assert "Answer briefly." in result.output


async def test_a_platform_is_chosen_from_the_environment_at_first_build() -> None:
    async with await _kernel(AI_TEST_CHAT_PLATFORM="offline").boot() as booted:
        result = await (await _agent(booted, "chat")).run("hi")

    assert result.output == "offline answer"


async def test_an_unknown_platform_from_the_environment_is_unavailable() -> None:
    async with await _kernel(AI_TEST_CHAT_PLATFORM="nope").boot() as booted:
        with pytest.raises(Exception) as raised:  # noqa: PT011 — the container wraps the cause
            _ = await _agent(booted, "chat")

    assert _cause(raised.value, PlatformUnavailableError) is not None


async def test_nothing_is_built_until_used_and_a_missing_key_names_its_variable() -> None:
    async with await _kernel(AI_TEST_KEY="").boot() as booted:
        registry = await booted.container.get(PlatformRegistry)
        assert registry._built == {}

    async with await _kernel().boot() as booted:
        registry = await booted.container.get(PlatformRegistry)
        with pytest.raises(PlatformUnavailableError, match='"AI_TEST_KEY" environment variable'):
            _ = await registry.get("keyed")


async def test_the_default_store_is_injected_with_and_without_its_name() -> None:
    async with await _kernel().boot() as booted:
        named = await booted.container.get(ConversationStore, "default")
        unnamed = await booted.container.get(ConversationStore)

    assert named is unnamed
    assert isinstance(named, InMemoryConversationStore)


async def test_run_control_is_registered() -> None:
    async with await _kernel().boot() as booted:
        control = await booted.container.get(RunControlInterface)
        _ = await control.start("r1", agent="chat", conversation_id="c1")
        async with control.watch("r1", CancellationToken()):
            pass
        status = await control.get("r1")

    assert status is not None
    assert status.state is RunState.FINISHED


async def test_the_clock_and_the_ai_channel_are_wired_in_when_their_bundles_are_active() -> None:
    async with await _kernel().boot() as booted:
        research = await _agent(booted, "research")
        channel = await booted.container.get(LoggerInterface, AI_CHANNEL)

    kinds = {type(capability) for capability in research.root_capability.capabilities}
    assert {RunClock, RunLogging} <= kinds
    assert channel is not None


async def test_agents_and_run_control_build_without_the_clock_and_logging_bundles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def without_peers(builder: ContainerBuilder, name: str) -> bool:
        return False if name in {"clock", "logging"} else bundle_active(builder, name)

    monkeypatch.setattr("xtr_ai.bundle.ai_bundle.bundle_active", without_peers)

    async with await _kernel().boot() as booted:
        research = await _agent(booted, "research")
        result = await research.run("hi")
        control = await booted.container.get(RunControlInterface)
        _ = await control.start("r1", agent="research")

    kinds = {type(capability) for capability in research.root_capability.capabilities}
    assert result.output == "offline answer"
    assert not kinds & {RunClock, RunLogging}


def test_building_and_booting_imports_no_provider_sdk() -> None:
    probe = (
        "import asyncio, sys\n"
        "from xtr_dependency_injection import Kernel\n"
        "async def main():\n"
        f"    async with await Kernel({APP!r}, env='test').boot():\n"
        "        pass\n"
        "asyncio.run(main())\n"
        "print(sorted(m for m in ('openai', 'anthropic', 'google.genai') if m in sys.modules))\n"
    )

    output = subprocess.run(
        [sys.executable, "-W", "ignore", "-c", probe],
        check=True,
        capture_output=True,
        text=True,
        cwd=Path(__file__).parents[3],
    ).stdout

    assert output.strip().splitlines()[-1] == "[]"


def _cause(error: BaseException, kind: type[BaseException]) -> BaseException | None:
    seen: BaseException | None = error
    while seen is not None:
        if isinstance(seen, kind):
            return seen
        seen = seen.__cause__ or seen.__context__
    return None

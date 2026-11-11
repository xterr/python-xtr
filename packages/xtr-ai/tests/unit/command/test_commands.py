from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_console import Application, ApplicationTester, ExitCode
from xtr_dependency_injection import Kernel

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from xtr_dependency_injection import BootedKernel

pytestmark = pytest.mark.anyio

KEY_SENTINEL = "sk-command-sentinel-1234"


@pytest.fixture
async def booted() -> AsyncIterator[BootedKernel]:
    kernel = Kernel("tests.fixtures.app_ai", env="test", environ={"AI_TEST_KEY": KEY_SENTINEL})
    async with await kernel.boot() as booted:
        yield booted


@pytest.fixture
async def tester(booted: BootedKernel) -> ApplicationTester:
    return ApplicationTester(await booted.container.get(Application), width=200)


async def test_debug_ai_lists_platforms_and_agents_without_any_secret(
    tester: ApplicationTester,
) -> None:
    assert await tester.execute(["debug:ai"]) == ExitCode.SUCCESS

    display = tester.display
    assert "env(AI_TEST_KEY)" in display
    assert KEY_SENTINEL not in display
    assert "env(AI_TEST_CHAT_PLATFORM)" in display
    assert "offline:backup" in display
    assert "Greeting" in display
    assert "Thinking" in display
    assert "agent research" in display


async def test_a_platform_answers_one_message(tester: ApplicationTester) -> None:
    assert await tester.execute(["ai:platform:invoke", "offline", "m", "hello"]) == ExitCode.SUCCESS

    assert "offline answer" in tester.display
    assert "input tokens" in tester.display


async def test_an_unknown_platform_is_an_error(tester: ApplicationTester) -> None:
    assert await tester.execute(["ai:platform:invoke", "nope", "m", "hi"]) == ExitCode.FAILURE

    assert '"nope" platform is unavailable' in tester.display + tester.error_display


async def test_a_single_request_carries_the_platforms_settings(tester: ApplicationTester) -> None:
    code = await tester.execute(["ai:platform:invoke", "echo_settings", "m", "hi"])

    assert code == ExitCode.SUCCESS
    assert "'max_tokens': 7" in tester.display


async def test_an_agent_holds_a_conversation_until_an_empty_line(
    tester: ApplicationTester,
) -> None:
    code = await tester.execute(["ai:agent:call", "research"], inputs=["first", "second", ""])

    assert code == ExitCode.SUCCESS
    assert tester.display.count("offline answer") == 2


async def test_calling_an_unknown_agent_is_refused(tester: ApplicationTester) -> None:
    assert await tester.execute(["ai:agent:call", "ghost"], inputs=[""]) == ExitCode.INVALID

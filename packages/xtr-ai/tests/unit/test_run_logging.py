from __future__ import annotations

from typing import TYPE_CHECKING

import anyio
import pytest
from pydantic_ai import Agent
from pydantic_ai.capabilities import ResolveModelId
from pydantic_ai.exceptions import RunTimedOut
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from xtr_logging_contracts import Level

from tests.support.recording_logger import RecordingLogger
from xtr_ai.platform import Platform
from xtr_ai.platform_registry import PlatformRegistry
from xtr_ai.run_logging import RunLogging

if TYPE_CHECKING:
    from pydantic_ai.models.function import AgentInfo

pytestmark = pytest.mark.anyio

PROMPT_SENTINEL = "prompt-sentinel-7f3a"
OUTPUT_SENTINEL = "output-sentinel-91bc"


def _answer(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    del messages, info
    return ModelResponse(parts=[TextPart(OUTPUT_SENTINEL)], finish_reason="stop")


def _fail(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    del messages, info
    raise RuntimeError(PROMPT_SENTINEL)


async def _slow(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    del messages, info
    await anyio.sleep(5)
    return ModelResponse(parts=[TextPart("late")])


def _agent(logger: RecordingLogger, platform: Platform) -> Agent[None, str]:
    registry = PlatformRegistry.of(platform)
    return Agent(
        f"{platform.name}:scripted",
        name="chat",
        instructions=f"instructions {PROMPT_SENTINEL}",
        capabilities=[ResolveModelId(registry.resolve), RunLogging(logger, registry)],
    )


async def test_a_response_and_the_runs_end_are_logged_with_counts_and_ids() -> None:
    logger = RecordingLogger()
    agent = _agent(logger, Platform("local", "function", options={"function": _answer}))

    _ = await agent.run(PROMPT_SENTINEL, conversation_id="c-1")

    (response_level, _, response), (run_level, _, run) = logger.records
    assert response_level is Level.DEBUG
    assert response["platform"] == "local"
    assert response["agent"] == "chat"
    assert response["model"] == "scripted"
    assert response["conversation_id"] == "c-1"
    assert response["finish_reason"] == "stop"
    assert run_level is Level.INFO
    assert run["requests"] == 1
    assert run["run_id"] is not None


async def test_no_prompt_instruction_or_output_is_ever_logged() -> None:
    logger = RecordingLogger()
    agent = _agent(logger, Platform("local", "function", options={"function": _answer}))

    _ = await agent.run(PROMPT_SENTINEL)

    assert PROMPT_SENTINEL not in logger.everything()
    assert OUTPUT_SENTINEL not in logger.everything()


async def test_a_failed_run_logs_the_errors_type_only() -> None:
    logger = RecordingLogger()
    agent = _agent(logger, Platform("local", "function", options={"function": _fail}))

    with pytest.raises(RuntimeError):
        _ = await agent.run("hi")

    level, _, context = logger.records[-1]
    assert level is Level.WARNING
    assert context["error"] == "RuntimeError"
    assert PROMPT_SENTINEL not in logger.everything()


async def test_a_cancelled_run_is_logged_as_cancelled_not_failed() -> None:
    logger = RecordingLogger()
    agent = _agent(logger, Platform("local", "function", options={"function": _slow}))

    with pytest.raises(RunTimedOut):
        _ = await agent.run("hi", timeout=0.05)

    level, message, _ = logger.records[-1]
    assert level is Level.INFO
    assert message == "The agent run was cancelled."


async def test_without_a_registry_no_platform_is_named() -> None:
    logger = RecordingLogger()
    registry = PlatformRegistry.of(Platform("local", "test"))
    agent = Agent("local:m", capabilities=[ResolveModelId(registry.resolve), RunLogging(logger)])

    _ = await agent.run("hi")

    assert all(context["platform"] is None for _, _, context in logger.records)
    assert RunLogging.get_serialization_name() is None

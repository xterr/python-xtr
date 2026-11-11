"""Offline platforms, two agents calling each other one way, and a store."""

from __future__ import annotations

from pydantic_ai.usage import UsageLimits
from xtr_dependency_injection import configure, env

from tests.fixtures.app_ai.services import Greeting, echo_settings, scripted
from xtr_ai.bundle import (
    AgentConfig,
    AgentToolRef,
    AiConfig,
    InMemoryConversationStoreConfig,
    ModelRef,
    PlatformConfig,
)


@configure
def ai() -> AiConfig:
    return AiConfig(
        platforms={
            "scripted": PlatformConfig(provider="function", options={"function": scripted}),
            "offline": PlatformConfig(
                provider="test",
                options={"custom_output_text": "offline answer"},
                model_settings={"temperature": 0.3},
            ),
            "echo_settings": PlatformConfig(
                provider="function",
                options={"function": echo_settings},
                model_settings={"max_tokens": 7},
            ),
            "keyed": PlatformConfig(provider="openai", api_key=env("AI_TEST_KEY")),
        },
        agents={
            "chat": AgentConfig(
                platform=env("AI_TEST_CHAT_PLATFORM", default="scripted"),
                model="script",
                fallbacks=(ModelRef("offline", "backup"),),
                instructions="Answer briefly.",
                capabilities=(Greeting, {"Thinking": {"effort": "low"}}),
                toolsets=(AgentToolRef(agent="research"),),
                usage_limits=UsageLimits(request_limit=5),
            ),
            "research": AgentConfig(
                platform="offline",
                model="research",
                instructions_file="%kernel.project_dir%/tests/fixtures/app_ai/prompts/research.md",
            ),
        },
        conversation_stores={"default": InMemoryConversationStoreConfig()},
    )

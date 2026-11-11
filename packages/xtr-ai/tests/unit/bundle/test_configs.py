from __future__ import annotations

import pytest
from xtr_dependency_injection import env

from xtr_ai.bundle import AgentConfig, AiConfig, ModelRef, PlatformConfig
from xtr_ai.exception import InvalidConfigurationError


def test_the_default_configuration_declares_nothing() -> None:
    config = AiConfig()

    assert config.platforms == {}
    assert config.agents == {}
    assert config.conversation_stores == {}
    assert config.runs is None


def test_a_platform_needs_a_provider() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = PlatformConfig(provider="")


def test_a_platforms_key_is_never_shown() -> None:
    assert "sk-secret" not in repr(PlatformConfig(provider="openai", api_key="sk-secret"))


def test_an_agent_takes_one_kind_of_instructions() -> None:
    with pytest.raises(InvalidConfigurationError, match="not both"):
        _ = AgentConfig(platform="p", model="m", instructions="a", instructions_file="b")


@pytest.mark.parametrize(
    ("platform", "model", "timeout"),
    [("", "m", None), ("p", "", None), ("p", "m", 0.0)],
)
def test_an_unusable_literal_is_refused(platform: str, model: str, timeout: float | None) -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = AgentConfig(platform=platform, model=model, timeout=timeout)


def test_placeholders_are_left_to_be_checked_when_read() -> None:
    agent = AgentConfig(platform=env("AI_PLATFORM"), model=env("AI_MODEL"))

    assert agent.platform is not None


def test_model_ids_join_platform_and_model() -> None:
    assert ModelRef("local", "llama").model_id == "local:llama"
    assert AgentConfig(platform="p", model="m").model_id == "p:m"

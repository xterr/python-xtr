from __future__ import annotations

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from xtr_ai._platform_model import PlatformModel
from xtr_ai.exception import InvalidConfigurationError, PlatformUnavailableError
from xtr_ai.platform import Platform


def _reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    del messages, info
    return ModelResponse(parts=[TextPart("hello")])


def test_a_name_and_a_provider_are_required() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = Platform("", "openai")
    with pytest.raises(InvalidConfigurationError, match='"p" platform needs a provider'):
        _ = Platform("p", "")


def test_nothing_is_built_until_a_model_is_asked_for() -> None:
    platform = Platform("p", "openai", api_key="sk-secret")

    assert platform._provider_instance is None
    assert platform._models == {}


def test_the_repr_never_shows_the_key() -> None:
    assert "sk-secret" not in repr(Platform("p", "openai", api_key="sk-secret"))


def test_a_test_platform_builds_a_test_model_from_its_options() -> None:
    platform = Platform("t", "test", options={"custom_output_text": "hi"})

    model = platform.model("any")

    assert isinstance(model, TestModel)
    assert model.custom_output_text == "hi"
    assert model.model_name == "any"
    assert platform.is_offline


def test_a_model_is_built_once() -> None:
    platform = Platform("t", "test")

    assert platform.model("a") is platform.model("a")
    assert platform.model("a") is not platform.model("b")


def test_a_function_platform_builds_a_function_model() -> None:
    platform = Platform("f", "function", options={"function": _reply})

    model = platform.model("scripted")

    assert isinstance(model, FunctionModel)
    assert model.model_name == "scripted"


def test_a_function_platform_needs_a_function() -> None:
    with pytest.raises(PlatformUnavailableError, match='options\\["function"\\]'):
        _ = Platform("f", "function").model("m")


def test_an_offline_platform_has_no_provider() -> None:
    with pytest.raises(PlatformUnavailableError, match="in process"):
        _ = Platform("t", "test").provider_instance()


def test_an_unknown_provider_is_unavailable() -> None:
    with pytest.raises(PlatformUnavailableError, match='no provider named "nope"') as raised:
        _ = Platform("x", "nope").model("m")

    assert raised.value.platform == "x"


def test_a_provider_is_built_once_and_shared_by_its_models() -> None:
    _ = pytest.importorskip("openai")
    platform = Platform("o", "openai", api_key="sk-secret")

    first = platform.model("gpt-5-mini")
    second = platform.model("gpt-5")

    assert platform.provider_instance() is platform.provider_instance()
    assert first.model_name == "gpt-5-mini"
    assert second.model_name == "gpt-5"


def test_a_keyword_the_provider_refuses_is_named_without_its_value() -> None:
    _ = pytest.importorskip("openai")
    platform = Platform("o", "openai", api_key="sk-secret", options={"region": "eu-secret"})

    with pytest.raises(PlatformUnavailableError) as raised:
        _ = platform.model("gpt-5")

    message = str(raised.value)
    assert "'region'" in message
    assert "sk-secret" not in message
    assert "eu-secret" not in message
    assert raised.value.__cause__ is None


def test_a_provider_refusing_its_configuration_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = pytest.importorskip("openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    platform = Platform("local", "openai", api_key="", base_url="http://localhost:11434/v1")

    with pytest.raises(PlatformUnavailableError, match="refused its configuration") as raised:
        _ = platform.model("llama")

    assert raised.value.platform == "local"


def test_platform_settings_travel_with_the_model_under_its_own() -> None:
    platform = Platform("t", "test", model_settings={"temperature": 0.1, "max_tokens": 10})

    model = platform.model("m")

    assert isinstance(model, PlatformModel)
    assert model.settings == {"temperature": 0.1, "max_tokens": 10}
    assert model.model_name == "m"


def test_the_wrapped_models_own_settings_win_over_the_platforms() -> None:
    model = PlatformModel(TestModel(settings={"temperature": 0.9}), {"temperature": 0.1})

    assert model.settings == {"temperature": 0.9}


@pytest.mark.anyio
async def test_closing_a_platform_that_built_nothing_does_nothing() -> None:
    platform = Platform("o", "openai", api_key="sk")

    await platform.aclose()

    assert platform._provider_instance is None


@pytest.mark.anyio
async def test_closing_a_platform_closes_its_providers_client() -> None:
    _ = pytest.importorskip("openai")
    platform = Platform("o", "openai", api_key="sk")
    provider = platform.provider_instance()

    await platform.aclose()

    own_client = provider._own_http_client
    assert own_client is None or own_client.is_closed

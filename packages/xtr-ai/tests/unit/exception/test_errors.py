from __future__ import annotations

from xtr_ai.exception import AiError, InvalidConfigurationError, PlatformUnavailableError


def test_every_error_derives_from_the_base() -> None:
    errors: list[AiError] = [
        InvalidConfigurationError("x"),
        PlatformUnavailableError("openai", "no key"),
    ]

    assert all(isinstance(error, AiError) for error in errors)


def test_platform_unavailable_names_the_platform_and_reason() -> None:
    error = PlatformUnavailableError("openai", "the OPENAI_API_KEY variable is not set")

    assert error.platform == "openai"
    assert str(error) == (
        'The "openai" platform is unavailable: the OPENAI_API_KEY variable is not set'
    )

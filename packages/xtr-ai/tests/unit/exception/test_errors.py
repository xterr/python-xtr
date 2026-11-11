from __future__ import annotations

from xtr_ai.exception import (
    AiError,
    InvalidConfigurationError,
    PlatformUnavailableError,
    RunInProgressError,
    UnknownRunError,
)


def test_every_error_derives_from_the_base() -> None:
    errors: list[AiError] = [
        InvalidConfigurationError("x"),
        PlatformUnavailableError("openai", "no key"),
        RunInProgressError("c1"),
        UnknownRunError("r1"),
    ]

    assert all(isinstance(error, AiError) for error in errors)


def test_platform_unavailable_names_the_platform_and_reason() -> None:
    error = PlatformUnavailableError("openai", "the OPENAI_API_KEY variable is not set")

    assert error.platform == "openai"
    assert str(error) == (
        'The "openai" platform is unavailable: the OPENAI_API_KEY variable is not set'
    )


def test_run_in_progress_names_the_holder_when_known() -> None:
    assert "by run" not in str(RunInProgressError("c1"))
    assert 'by run "r1"' in str(RunInProgressError("c1", "r1"))


def test_unknown_run_is_a_lookup_error() -> None:
    assert isinstance(UnknownRunError("r1"), LookupError)

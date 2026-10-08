from __future__ import annotations

from pathlib import Path

import pytest

from xtr_cli.exception import (
    CliError,
    DirectoryNotEmptyError,
    InvalidProjectNameError,
    InvalidTemplateError,
    StepFailedError,
    UnknownAddOnError,
    UnknownTemplateError,
    UnsupportedPythonError,
)


@pytest.mark.parametrize(
    "error",
    [
        DirectoryNotEmptyError(Path("shop"), ("a",)),
        InvalidProjectNameError("x", "why"),
        InvalidTemplateError("t", "why"),
        StepFailedError(("uv",), Path(), 1),
        UnknownAddOnError("x", "why"),
        UnknownTemplateError("x", ("cli",)),
        UnsupportedPythonError("3.9"),
    ],
    ids=lambda error: type(error).__name__,  # pyright: ignore[reportAny] — pytest types ids loosely.
)
def test_every_error_is_a_cli_error(error: CliError) -> None:
    assert isinstance(error, CliError)

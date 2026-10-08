from __future__ import annotations

from pathlib import Path

from xtr_cli.exception import StepFailedError


def test_it_names_the_command_its_code_and_where_it_ran() -> None:
    error = StepFailedError(("uv", "add", "x"), Path("shop"), 2)

    assert str(error) == "`uv add x` exited with 2 in shop"

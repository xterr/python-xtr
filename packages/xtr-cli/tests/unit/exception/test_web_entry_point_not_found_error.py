from __future__ import annotations

from pathlib import Path

from xtr_cli.exception import CliError, WebEntryPointNotFoundError


def test_it_names_the_project_and_what_it_lacks() -> None:
    error = WebEntryPointNotFoundError(Path("shop"), "no script 'web'")

    assert isinstance(error, CliError)
    assert str(error) == "nothing to serve in shop: no script 'web'"

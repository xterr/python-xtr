from __future__ import annotations

from pathlib import Path

from xtr_cli.exception import CliError, ProjectNotFoundError


def test_it_names_where_it_looked_and_the_option_to_pass() -> None:
    error = ProjectNotFoundError(Path("/somewhere"))

    assert isinstance(error, CliError)
    assert str(error) == "no pyproject.toml in /somewhere or above it: pass --project-dir"

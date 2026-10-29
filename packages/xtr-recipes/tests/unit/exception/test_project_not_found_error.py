from __future__ import annotations

from pathlib import Path

from xtr_recipes.exception import ProjectNotFoundError, RecipesError


def test_it_derives_from_the_base() -> None:
    assert issubclass(ProjectNotFoundError, RecipesError)


def test_it_keeps_the_directory_and_reason() -> None:
    error = ProjectNotFoundError(Path("/x"), "no pyproject.toml here")

    assert error.directory == Path("/x")
    assert error.reason == "no pyproject.toml here"
    assert str(error) == "no application project at /x: no pyproject.toml here"

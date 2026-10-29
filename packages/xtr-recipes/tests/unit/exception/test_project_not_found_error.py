from __future__ import annotations

from pathlib import Path

from xtr_recipes.exception import ProjectNotFoundError, RecipesError


def test_it_derives_from_the_base() -> None:
    assert issubclass(ProjectNotFoundError, RecipesError)


def test_it_keeps_the_directory_reason_and_setting() -> None:
    error = ProjectNotFoundError(Path("/x"), "no longer read", "[tool.xtr-recipes] app")

    assert error.directory == Path("/x")
    assert error.reason == "no longer read"
    assert error.setting == "[tool.xtr-recipes] app"


def test_its_message_names_the_setting_when_given() -> None:
    message = str(ProjectNotFoundError(Path("/x"), "no longer read", "[tool.xtr-recipes] app"))

    assert "[tool.xtr-recipes] app" in message


def test_the_setting_is_optional() -> None:
    error = ProjectNotFoundError(Path("/x"), "no pyproject.toml here or above")

    assert error.setting is None
    assert "setting" not in str(error)

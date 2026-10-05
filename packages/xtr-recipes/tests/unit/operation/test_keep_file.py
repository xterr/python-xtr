from __future__ import annotations

from xtr_recipes.operation.keep_file import KeepFile


def test_it_renders_the_path_and_the_reason() -> None:
    assert KeepFile("src/app/config/messenger.py", "edited").render() == (
        "  kept src/app/config/messenger.py (edited)",
    )


def test_it_renders_an_adopted_file() -> None:
    assert KeepFile(".env", "adopted").render() == ("  kept .env (adopted)",)


def test_it_changes_nothing() -> None:
    assert KeepFile.changes is False


def test_applying_it_leaves_the_project_alone() -> None:
    assert KeepFile("config.py", "edited").apply() is None

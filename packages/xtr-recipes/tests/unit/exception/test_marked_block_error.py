from __future__ import annotations

from pathlib import Path

from xtr_recipes.exception import MarkedBlockError, RecipesError


def test_it_derives_from_the_base() -> None:
    assert issubclass(MarkedBlockError, RecipesError)


def test_it_is_a_value_error() -> None:
    assert issubclass(MarkedBlockError, ValueError)


def test_it_keeps_the_file_and_the_reason() -> None:
    error = MarkedBlockError(Path("/x/.env"), "never closed")

    assert error.path_or_name == Path("/x/.env")
    assert error.reason == "never closed"


def test_its_message_names_both() -> None:
    assert str(MarkedBlockError("xtr-messenger", "never closed")) == ("xtr-messenger: never closed")

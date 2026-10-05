from __future__ import annotations

from xtr_recipes.exception import RecipesError


def test_it_is_an_exception() -> None:
    assert issubclass(RecipesError, Exception)


def test_it_carries_its_message() -> None:
    assert str(RecipesError("boom")) == "boom"

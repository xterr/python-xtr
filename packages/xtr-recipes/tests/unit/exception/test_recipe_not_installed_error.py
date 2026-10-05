from __future__ import annotations

from xtr_recipes.exception import RecipeNotInstalledError, RecipesError


def test_it_carries_the_package_that_was_named() -> None:
    assert RecipeNotInstalledError("xtr-orm").package == "xtr-orm"


def test_its_message_names_the_package() -> None:
    assert "xtr-orm" in str(RecipeNotInstalledError("xtr-orm"))


def test_it_is_one_of_this_librarys_errors() -> None:
    assert isinstance(RecipeNotInstalledError("xtr-orm"), RecipesError)

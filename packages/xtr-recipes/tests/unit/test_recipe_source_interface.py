from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_recipes.recipe_source_interface import RecipeSourceInterface

if TYPE_CHECKING:
    from xtr_recipes.recipe_content import RecipeContent


class _Conforming:
    def load(self) -> dict[str, RecipeContent]:
        return {}


def test_an_object_with_load_is_a_recipe_source() -> None:
    assert isinstance(_Conforming(), RecipeSourceInterface)


def test_an_object_without_load_is_not_a_recipe_source() -> None:
    assert not isinstance(object(), RecipeSourceInterface)

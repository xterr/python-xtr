from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_recipes.recipe_content import RecipeContent

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["FakeRecipeSource", "recipe_content"]


@final
class FakeRecipeSource:
    """A recipe source holding manifests and templates written in a test."""

    def __init__(self, recipes: Mapping[str, RecipeContent] | None = None) -> None:
        self._recipes: dict[str, RecipeContent] = dict(recipes) if recipes else {}

    def load(self) -> Mapping[str, RecipeContent]:
        return self._recipes


def recipe_content(manifest: str, templates: Mapping[str, str] | None = None) -> RecipeContent:
    """Build one recipe's raw content from the text a test writes inline."""
    return RecipeContent(
        manifest=manifest.encode("utf-8"),
        templates={path: text.encode("utf-8") for path, text in (templates or {}).items()},
    )

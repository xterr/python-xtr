from __future__ import annotations

from xtr_recipes.recipe_content import RecipeContent


def test_it_holds_the_manifest_and_templates() -> None:
    content = RecipeContent(manifest=b"[bundles]\n", templates={"a.tmpl": b"body"})

    assert content.manifest == b"[bundles]\n"
    assert content.templates == {"a.tmpl": b"body"}

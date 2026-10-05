from __future__ import annotations

from typing import final

import pytest

from tests.support import FakeRecipeSource, recipe_content
from xtr_recipes import entry_point_recipe_source as eps
from xtr_recipes.exception import InvalidManifestError
from xtr_recipes.recipe_content import RecipeContent
from xtr_recipes.recipe_loader import RecipeLoader

_MANIFEST = (
    b"[bundles]\n"
    b'"xtr_messenger.bundle:MessengerBundle" = { all = true }\n\n'
    b"[files]\n"
    b'"config/messenger.py" = "files/config/messenger.py.tmpl"\n'
)
_TEMPLATE_PATH = "files/config/messenger.py.tmpl"
_TEMPLATE = b"MESSENGER = ${app}\n"


@final
class _FakeSource:
    def __init__(self, recipes: dict[str, RecipeContent]) -> None:
        self._recipes = recipes

    def load(self) -> dict[str, RecipeContent]:
        return self._recipes


def _content(
    manifest: bytes = _MANIFEST,
    templates: dict[str, bytes] | None = None,
) -> RecipeContent:
    return RecipeContent(
        manifest=manifest,
        templates={_TEMPLATE_PATH: _TEMPLATE} if templates is None else templates,
    )


def test_it_loads_and_parses_a_recipe() -> None:
    (recipe,) = RecipeLoader(_FakeSource({"xtr-messenger": _content()})).load()

    assert recipe.distribution == "xtr-messenger"
    assert recipe.config.bundles == {"xtr_messenger.bundle:MessengerBundle": {"all": True}}


def test_it_sorts_recipes_by_distribution() -> None:
    loader = RecipeLoader(_FakeSource({"b-pkg": _content(), "a-pkg": _content()}))

    assert [recipe.distribution for recipe in loader.load()] == ["a-pkg", "b-pkg"]


def test_it_renders_a_template_substituting_the_app() -> None:
    (recipe,) = RecipeLoader(_FakeSource({"xtr-messenger": _content()})).load()

    assert recipe.render(_TEMPLATE_PATH, app="bookshop") == "MESSENGER = bookshop\n"


def test_render_rejects_an_unknown_placeholder() -> None:
    (recipe,) = RecipeLoader(_FakeSource({"x": _content(templates={"t.tmpl": b"${nope}"})})).load()

    with pytest.raises(InvalidManifestError) as exc:
        _ = recipe.render("t.tmpl", app="a")

    assert exc.value.key == "t.tmpl"
    assert "nope" in exc.value.reason


def test_render_rejects_a_malformed_placeholder() -> None:
    (recipe,) = RecipeLoader(_FakeSource({"x": _content(templates={"t.tmpl": b"$ bad"})})).load()

    with pytest.raises(InvalidManifestError):
        _ = recipe.render("t.tmpl", app="a")


def test_render_rejects_an_unknown_template() -> None:
    (recipe,) = RecipeLoader(_FakeSource({"x": _content()})).load()

    with pytest.raises(InvalidManifestError) as exc:
        _ = recipe.render("missing.tmpl", app="a")

    assert "no such template" in exc.value.reason


def test_the_hash_is_stable_across_loads() -> None:
    source = _FakeSource({"x": _content()})

    first = RecipeLoader(source).load()[0].recipe_hash
    second = RecipeLoader(source).load()[0].recipe_hash

    assert first == second


def test_the_hash_changes_when_a_template_changes() -> None:
    base = RecipeLoader(_FakeSource({"x": _content()})).load()[0].recipe_hash
    other = _content(templates={_TEMPLATE_PATH: b"MESSENGER = ${app}  # changed\n"})

    changed = RecipeLoader(_FakeSource({"x": other})).load()[0].recipe_hash

    assert base != changed


def test_the_hash_changes_when_the_manifest_changes() -> None:
    base = RecipeLoader(_FakeSource({"x": _content()})).load()[0].recipe_hash

    changed = (
        RecipeLoader(_FakeSource({"x": _content(manifest=b'[env]\nKEY = ""\n')}))
        .load()[0]
        .recipe_hash
    )

    assert base != changed


def _no_entries(group: str) -> list[object]:
    assert group == "xtr_recipes"
    return []


def test_the_default_source_is_the_advertised_entry_points(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(eps, "entry_points", _no_entries)

    assert RecipeLoader().load() == ()


def test_a_manifest_that_is_not_toml_is_an_invalid_manifest() -> None:
    source = FakeRecipeSource({"xtr-broken": recipe_content("[bundles\n")})

    with pytest.raises(InvalidManifestError):
        _ = RecipeLoader(source).load()

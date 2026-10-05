from __future__ import annotations

from xtr_recipes.recipe_config import RecipeConfig
from xtr_recipes.recipe_loader import Recipe
from xtr_recipes.recipe_lock import LockEntry, RecipeLock
from xtr_recipes.sync_selection import SyncSelection


def _recipe(distribution: str, recipe_hash: str) -> Recipe:
    return Recipe(
        distribution=distribution,
        config=RecipeConfig(),
        templates={},
        recipe_hash=recipe_hash,
    )


def test_an_installed_package_the_lock_does_not_have_is_configured() -> None:
    selection = SyncSelection.diff({"xtr-messenger": _recipe("xtr-messenger", "a")}, RecipeLock())

    assert selection.configure == ("xtr-messenger",)
    assert selection.update == ()


def test_a_locked_package_no_longer_installed_is_unconfigured() -> None:
    lock = RecipeLock({"xtr-messenger": LockEntry(recipe="a")})

    assert SyncSelection.diff({}, lock).unconfigure == ("xtr-messenger",)


def test_locked_packages_are_unconfigured_in_reverse_lock_order() -> None:
    lock = RecipeLock({"a-pkg": LockEntry(), "b-pkg": LockEntry(), "c-pkg": LockEntry()})

    assert SyncSelection.diff({}, lock).unconfigure == ("c-pkg", "b-pkg", "a-pkg")


def test_a_package_whose_recipe_moved_on_is_updated() -> None:
    lock = RecipeLock({"xtr-messenger": LockEntry(recipe="old")})

    selection = SyncSelection.diff({"xtr-messenger": _recipe("xtr-messenger", "new")}, lock)

    assert selection.update == ("xtr-messenger",)
    assert selection.unchanged == ()


def test_a_package_with_the_same_recipe_is_left_unchanged() -> None:
    lock = RecipeLock({"xtr-messenger": LockEntry(recipe="same")})

    selection = SyncSelection.diff({"xtr-messenger": _recipe("xtr-messenger", "same")}, lock)

    assert selection.unchanged == ("xtr-messenger",)
    assert selection.update == ()


def test_packages_to_configure_are_sorted_by_name() -> None:
    installed = {name: _recipe(name, "a") for name in ("c-pkg", "a-pkg", "b-pkg")}

    assert SyncSelection.diff(installed, RecipeLock()).configure == ("a-pkg", "b-pkg", "c-pkg")


def test_naming_one_unlocked_package_configures_only_it() -> None:
    selection = SyncSelection.only("xtr-messenger", RecipeLock())

    assert selection == SyncSelection(configure=("xtr-messenger",))


def test_naming_one_locked_package_updates_it_whatever_its_hash() -> None:
    lock = RecipeLock({"xtr-messenger": LockEntry(recipe="same")})

    assert SyncSelection.only("xtr-messenger", lock) == SyncSelection(update=("xtr-messenger",))


def test_a_selection_of_nothing_is_the_default() -> None:
    assert SyncSelection.diff({}, RecipeLock()) == SyncSelection()

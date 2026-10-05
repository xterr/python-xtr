from __future__ import annotations

from xtr_recipes.operation.notes import Notes
from xtr_recipes.operation.section import Section
from xtr_recipes.planned_recipe import PlannedRecipe
from xtr_recipes.recipe_lock import LockedFile


def test_a_recipe_planning_nothing_has_every_field_empty() -> None:
    planned = PlannedRecipe()

    assert planned.operations == ()
    assert planned.notes is None
    assert planned.files == {}
    assert planned.env == ()
    assert planned.gitignore == ()


def test_it_holds_the_steps_and_what_the_lock_should_record() -> None:
    planned = PlannedRecipe(
        operations=(Section("configure", "xtr-messenger"),),
        notes=Notes(run=("app go",)),
        files={"src/app/config/messenger.py": LockedFile("abc", adopted=False)},
        env=("MESSENGER_DSN",),
        gitignore=("/var/messenger",),
    )

    assert planned.operations[0].render() == ("configure xtr-messenger",)
    assert planned.files["src/app/config/messenger.py"].sha256 == "abc"


def test_two_recipes_planning_the_same_thing_are_equal() -> None:
    assert PlannedRecipe(env=("A",)) == PlannedRecipe(env=("A",))

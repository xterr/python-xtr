from __future__ import annotations

from xtr_recipes.recipe_survey import RecipeSurvey
from xtr_recipes.sync_selection import SyncSelection


def test_a_survey_of_a_project_with_no_recipes_is_empty() -> None:
    survey = RecipeSurvey()

    assert survey.installed == {}
    assert survey.skipped == {}
    assert survey.selection == SyncSelection()


def test_a_survey_holds_what_it_was_built_with() -> None:
    skipped = {"xtr-security": ("xtr_security.bundle:SecurityBundle",)}
    selection = SyncSelection(configure=("xtr-clock",))

    survey = RecipeSurvey(skipped=skipped, selection=selection)

    assert survey.skipped == skipped
    assert survey.selection == selection

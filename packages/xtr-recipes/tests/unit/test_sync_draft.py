from __future__ import annotations

from dataclasses import replace

from xtr_recipes.operation.keep_file import KeepFile
from xtr_recipes.operation.notes import Notes
from xtr_recipes.planned_recipe import PlannedRecipe
from xtr_recipes.recipe_config import RecipeConfig
from xtr_recipes.recipe_loader import Recipe
from xtr_recipes.recipe_lock import LockedFile, LockEntry, RecipeLock
from xtr_recipes.sync_draft import SyncDraft
from xtr_recipes.sync_selection import SyncSelection

_MESSENGER = "xtr-messenger"
_TARGET = "xtr_messenger.bundle:MessengerBundle"
_FILE = "src/app/config/messenger.py"

_RECIPE = Recipe(
    distribution=_MESSENGER,
    config=RecipeConfig(bundles={_TARGET: {"all": True}}),
    templates={},
    recipe_hash="hash",
)
# One installed recipe putting one bundle forward, which nothing else requires.
_LISTING = SyncDraft(installed={_MESSENGER: _RECIPE}, states={_TARGET: "listed"})


def _lines(draft: SyncDraft) -> tuple[str, ...]:
    return tuple(line for step in draft.sections() for line in step.render())


def test_a_draft_of_nothing_reports_nothing() -> None:
    assert SyncDraft().sections() == ()


def test_a_draft_of_nothing_leaves_the_lock_empty() -> None:
    assert SyncDraft().next_lock() == RecipeLock({})


def test_configuring_reads_as_a_section_with_its_steps_and_notes() -> None:
    draft = replace(
        _LISTING,
        selection=SyncSelection(configure=(_MESSENGER,)),
        planned={
            _MESSENGER: PlannedRecipe(
                operations=(KeepFile(_FILE, "adopted"),),
                notes=Notes(run=("app go",)),
            )
        },
    )

    assert _lines(draft) == (
        f"configure {_MESSENGER}",
        f"  kept {_FILE} (adopted)",
        "  bundle MessengerBundle listed",
        "  run:",
        "    - app go",
    )


def test_configuring_records_the_recipe_hash_and_what_it_wrote() -> None:
    planned = PlannedRecipe(
        files={_FILE: LockedFile("abc", adopted=False)},
        env=("MESSENGER_DSN",),
        gitignore=("/var",),
    )
    draft = replace(
        _LISTING,
        selection=SyncSelection(configure=(_MESSENGER,)),
        planned={_MESSENGER: planned},
    )

    assert draft.next_lock().entries[_MESSENGER] == LockEntry(
        recipe="hash",
        bundles={_TARGET: "listed"},
        files={_FILE: LockedFile("abc", adopted=False)},
        env=("MESSENGER_DSN",),
        gitignore=("/var",),
    )


def test_unconfiguring_reads_as_a_section_and_drops_the_entry() -> None:
    draft = SyncDraft(
        selection=SyncSelection(unconfigure=(_MESSENGER,)),
        undone={_MESSENGER: (KeepFile(_FILE, "edited"),)},
        lock=RecipeLock({_MESSENGER: LockEntry(bundles={_TARGET: "listed"})}),
        listed=frozenset({_TARGET}),
    )

    assert _lines(draft) == (
        f"unconfigure {_MESSENGER}",
        f"  kept {_FILE} (edited)",
        "  bundle MessengerBundle removed",
    )
    assert draft.next_lock() == RecipeLock({})


def test_a_bundle_the_list_never_held_is_not_reported_as_removed() -> None:
    draft = SyncDraft(
        selection=SyncSelection(unconfigure=(_MESSENGER,)),
        undone={_MESSENGER: ()},
        lock=RecipeLock({_MESSENGER: LockEntry(bundles={_TARGET: "required"})}),
    )

    assert _lines(draft) == (f"unconfigure {_MESSENGER}",)


def test_skipping_reads_as_a_section_naming_the_extra_to_install() -> None:
    draft = SyncDraft(skipped={_MESSENGER: (_TARGET,)})

    assert _lines(draft) == (
        f"skip {_MESSENGER}",
        f"  bundle MessengerBundle skipped: install {_MESSENGER}[di]",
    )


def test_an_untouched_package_keeps_everything_but_its_bundle_standings() -> None:
    prior = LockEntry(
        recipe="hash",
        bundles={_TARGET: "required"},
        files={_FILE: LockedFile("abc", adopted=False)},
        env=("MESSENGER_DSN",),
    )
    draft = replace(
        _LISTING,
        selection=SyncSelection(unchanged=(_MESSENGER,)),
        lock=RecipeLock({_MESSENGER: prior}),
    )

    entry = draft.next_lock().entries[_MESSENGER]

    assert entry.bundles == {_TARGET: "listed"}
    assert entry.files == prior.files
    assert entry.env == prior.env


def test_an_untouched_package_is_not_reported() -> None:
    draft = replace(
        _LISTING,
        selection=SyncSelection(unchanged=(_MESSENGER,)),
        lock=RecipeLock({_MESSENGER: LockEntry(recipe="hash")}),
    )

    assert draft.sections() == ()


def test_a_bundle_this_package_once_listed_stays_listed() -> None:
    draft = replace(
        _LISTING,
        selection=SyncSelection(update=(_MESSENGER,)),
        planned={_MESSENGER: PlannedRecipe()},
        states={_TARGET: "adopted"},
        lock=RecipeLock({_MESSENGER: LockEntry(bundles={_TARGET: "listed"})}),
    )

    assert draft.next_lock().entries[_MESSENGER].bundles == {_TARGET: "listed"}


def test_a_bundle_the_owner_had_listed_first_stays_adopted() -> None:
    draft = replace(
        _LISTING,
        selection=SyncSelection(update=(_MESSENGER,)),
        planned={_MESSENGER: PlannedRecipe()},
        states={_TARGET: "adopted"},
        lock=RecipeLock({_MESSENGER: LockEntry(bundles={_TARGET: "adopted"})}),
    )

    assert draft.next_lock().entries[_MESSENGER].bundles == {_TARGET: "adopted"}


def test_a_bundle_left_out_is_recorded_as_required() -> None:
    draft = replace(
        _LISTING,
        selection=SyncSelection(configure=(_MESSENGER,)),
        planned={_MESSENGER: PlannedRecipe()},
        states={_TARGET: "required"},
    )

    assert draft.next_lock().entries[_MESSENGER].bundles == {_TARGET: "required"}

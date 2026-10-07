from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import pytest

from tests.support import build_project
from xtr_recipes.marked_block_editor import MarkedBlockEditor
from xtr_recipes.notes_config import NotesConfig
from xtr_recipes.operation.delete_file import DeleteFile
from xtr_recipes.operation.keep_file import KeepFile
from xtr_recipes.operation.move_file import MoveFile
from xtr_recipes.operation.notes import Notes
from xtr_recipes.operation.put_block import PutBlock
from xtr_recipes.operation.remove_block import RemoveBlock
from xtr_recipes.operation.write_file import WriteFile
from xtr_recipes.operation.write_new_file import WriteNewFile
from xtr_recipes.recipe_config import RecipeConfig
from xtr_recipes.recipe_loader import Recipe
from xtr_recipes.recipe_lock import LockedFile, LockEntry
from xtr_recipes.recipe_planner import RecipePlanner

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from xtr_recipes.project import Project

_PACKAGE = "xtr-messenger"
_DESTINATION = "config/messenger.py"
_TEMPLATE = "files/config/messenger.py.tmpl"
_BODY = "MESSENGER = ${app}\n"
_RENDERED = "MESSENGER = app\n"
_LOCKED = "src/app/config/messenger.py"
_CONFIG_INIT = "src/app/config/__init__.py"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _recipe(
    files: Mapping[str, str] | None = None,
    env: Mapping[str, str] | None = None,
    gitignore: tuple[str, ...] = (),
    notes: NotesConfig | None = None,
) -> Recipe:
    return Recipe(
        distribution=_PACKAGE,
        config=RecipeConfig(
            files={_DESTINATION: _TEMPLATE} if files is None else files,
            env=env or {},
            gitignore=gitignore,
            notes=notes or NotesConfig(),
        ),
        templates={_TEMPLATE: _BODY.encode("utf-8")},
        recipe_hash="hash",
    )


def _existing(project: Project, text: str, destination: str = _DESTINATION) -> Path:
    """Write a destination file, and the config package holding it, by hand."""
    path = project.package_dir / destination
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = (path.parent / "__init__.py").write_text("", encoding="utf-8")
    _ = path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def project(tmp_path: Path) -> Project:
    return build_project(tmp_path, dependencies=[_PACKAGE])


@pytest.fixture
def planner(project: Project) -> RecipePlanner:
    return RecipePlanner(project, MarkedBlockEditor())


def test_configure_writes_a_file_the_project_does_not_have(planner: RecipePlanner) -> None:
    planned = planner.configure(_recipe())

    assert [step.render() for step in planned.operations] == [
        (f"  write {_CONFIG_INIT}",),
        (f"  write {_LOCKED}",),
    ]


def test_configure_locks_the_content_it_wrote(planner: RecipePlanner) -> None:
    planned = planner.configure(_recipe())

    assert planned.files == {_LOCKED: LockedFile(_sha256(_RENDERED), adopted=False)}


def test_configure_creates_the_config_package_once(planner: RecipePlanner) -> None:
    first = planner.configure(_recipe())
    second = planner.configure(_recipe(files={"config/orm.py": _TEMPLATE}))

    assert any(isinstance(step, WriteFile) for step in first.operations)
    assert [step.render() for step in second.operations] == [("  write src/app/config/orm.py",)]


def test_an_existing_config_package_is_adopted_rather_than_written(
    planner: RecipePlanner,
    project: Project,
) -> None:
    (project.package_dir / "config").mkdir()
    _ = (project.package_dir / "config" / "__init__.py").write_text("", encoding="utf-8")

    planned = planner.configure(_recipe())

    assert [step.render() for step in planned.operations] == [(f"  write {_LOCKED}",)]


def test_the_config_package_is_never_locked(planner: RecipePlanner) -> None:
    assert _CONFIG_INIT not in planner.configure(_recipe()).files


def test_a_destination_outside_config_needs_no_config_package(planner: RecipePlanner) -> None:
    planned = planner.configure(_recipe(files={"settings.py": _TEMPLATE}))

    assert [step.render() for step in planned.operations] == [("  write src/app/settings.py",)]


def test_configure_adopts_a_file_the_project_already_has(
    planner: RecipePlanner,
    project: Project,
) -> None:
    _ = _existing(project, "MINE\n")

    planned = planner.configure(_recipe())

    assert planned.operations == (KeepFile(_LOCKED, "adopted"),)
    assert planned.files == {_LOCKED: LockedFile(_sha256("MINE\n"), adopted=True)}


def test_configure_writes_the_env_block_with_a_commented_default(
    planner: RecipePlanner,
    project: Project,
) -> None:
    planned = planner.configure(_recipe(env={"MESSENGER_DSN": ""}))

    assert planned.operations[-1] == PutBlock(
        project.project_dir / ".env",
        ".env",
        _PACKAGE,
        ("# MESSENGER_DSN=",),
    )
    assert planned.env == ("MESSENGER_DSN",)


def test_configure_adopts_an_env_key_the_project_already_sets(
    planner: RecipePlanner,
    project: Project,
) -> None:
    _ = (project.project_dir / ".env").write_text("MESSENGER_DSN=amqp://mine\n", encoding="utf-8")

    planned = planner.configure(_recipe(env={"MESSENGER_DSN": ""}))

    assert not any(isinstance(step, PutBlock) for step in planned.operations)
    assert planned.env == ()


def test_configure_writes_the_gitignore_block(planner: RecipePlanner) -> None:
    planned = planner.configure(_recipe(gitignore=("/var/lock",)))

    assert planned.operations[-1].render() == ("  write .gitignore",)
    assert planned.gitignore == ("/var/lock",)


def test_configure_adopts_an_ignore_line_already_there(
    planner: RecipePlanner,
    project: Project,
) -> None:
    _ = (project.project_dir / ".gitignore").write_text("/var/lock\n", encoding="utf-8")

    planned = planner.configure(_recipe(gitignore=("/var/lock",)))

    assert planned.gitignore == ()
    assert not any(isinstance(step, PutBlock) for step in planned.operations)


def test_a_recipe_with_nothing_to_say_plans_no_notes(planner: RecipePlanner) -> None:
    assert planner.configure(_recipe()).notes is None


def test_notes_resolve_the_script_placeholder(planner: RecipePlanner) -> None:
    notes = NotesConfig(check=("<script> debug:bundles",))

    assert planner.configure(_recipe(notes=notes)).notes == Notes(check=("app debug:bundles",))


def test_notes_keep_the_placeholder_when_the_application_has_no_script(tmp_path: Path) -> None:
    project = build_project(tmp_path, dependencies=[_PACKAGE], script=None)
    planner = RecipePlanner(project, MarkedBlockEditor())
    notes = NotesConfig(run=("<script> messenger:consume",))

    assert planner.configure(_recipe(notes=notes)).notes == Notes(
        run=("<script> messenger:consume",)
    )


def test_update_writes_a_file_that_went_missing(planner: RecipePlanner) -> None:
    prior = LockEntry(files={_LOCKED: LockedFile(_sha256(_RENDERED), adopted=False)})

    planned = planner.update(_recipe(), prior, force=False)

    assert any(isinstance(step, WriteFile) for step in planned.operations)


def test_update_overwrites_an_untouched_file(planner: RecipePlanner, project: Project) -> None:
    path = _existing(project, "OLD\n")
    prior = LockEntry(files={_LOCKED: LockedFile(_sha256("OLD\n"), adopted=False)})

    planned = planner.update(_recipe(), prior, force=False)

    assert planned.operations == (WriteFile(path, _LOCKED, _RENDERED),)
    assert planned.files == {_LOCKED: LockedFile(_sha256(_RENDERED), adopted=False)}


def test_update_leaves_an_untouched_file_alone_when_the_content_is_the_same(
    planner: RecipePlanner,
    project: Project,
) -> None:
    _ = _existing(project, _RENDERED)
    prior = LockEntry(files={_LOCKED: LockedFile(_sha256(_RENDERED), adopted=False)})

    planned = planner.update(_recipe(), prior, force=False)

    assert planned.operations == ()


def test_update_offers_a_new_file_beside_one_that_was_edited(
    planner: RecipePlanner,
    project: Project,
) -> None:
    path = _existing(project, "EDITED\n")
    locked = LockedFile(_sha256("ORIGINAL\n"), adopted=False)

    planned = planner.update(_recipe(), LockEntry(files={_LOCKED: locked}), force=False)

    assert planned.operations == (WriteNewFile(path, _LOCKED, _RENDERED),)
    assert planned.files == {_LOCKED: locked}


def test_update_offers_nothing_when_the_new_copy_already_holds_the_content(
    planner: RecipePlanner,
    project: Project,
) -> None:
    path = _existing(project, "EDITED\n")
    _ = (path.parent / f"{path.name}.new").write_text(_RENDERED, encoding="utf-8")
    locked = LockedFile(_sha256("ORIGINAL\n"), adopted=False)

    planned = planner.update(_recipe(), LockEntry(files={_LOCKED: locked}), force=False)

    assert planned.operations == ()


def test_update_overwrites_an_edited_file_when_forced(
    planner: RecipePlanner,
    project: Project,
) -> None:
    path = _existing(project, "EDITED\n")
    locked = LockedFile(_sha256("ORIGINAL\n"), adopted=False)

    planned = planner.update(_recipe(), LockEntry(files={_LOCKED: locked}), force=True)

    assert planned.operations == (WriteFile(path, _LOCKED, _RENDERED),)
    assert planned.files == {_LOCKED: LockedFile(_sha256(_RENDERED), adopted=False)}


def test_update_offers_a_new_file_beside_an_adopted_one(
    planner: RecipePlanner,
    project: Project,
) -> None:
    path = _existing(project, "MINE\n")
    locked = LockedFile(_sha256("MINE\n"), adopted=True)

    planned = planner.update(_recipe(), LockEntry(files={_LOCKED: locked}), force=False)

    assert planned.operations == (WriteNewFile(path, _LOCKED, _RENDERED),)
    assert planned.files == {_LOCKED: locked}


def test_update_offers_nothing_beside_an_adopted_file_that_already_matches(
    planner: RecipePlanner,
    project: Project,
) -> None:
    _ = _existing(project, _RENDERED)
    locked = LockedFile(_sha256(_RENDERED), adopted=True)

    planned = planner.update(_recipe(), LockEntry(files={_LOCKED: locked}), force=False)

    assert planned.operations == ()
    assert planned.files == {_LOCKED: locked}


def test_update_offers_nothing_beside_an_adopted_file_the_lock_never_recorded(
    planner: RecipePlanner,
    project: Project,
) -> None:
    _ = _existing(project, _RENDERED)

    planned = planner.update(_recipe(), LockEntry(), force=False)

    assert planned.operations == (KeepFile(_LOCKED, "adopted"),)


def test_update_adopts_a_destination_the_manifest_has_only_just_added(
    planner: RecipePlanner,
    project: Project,
) -> None:
    _ = _existing(project, "MINE\n")

    planned = planner.update(_recipe(), LockEntry(), force=False)

    assert planned.files == {_LOCKED: LockedFile(_sha256("MINE\n"), adopted=True)}
    assert planned.operations == (KeepFile(_LOCKED, "adopted"),)


def test_update_deletes_a_file_the_manifest_dropped(
    planner: RecipePlanner,
    project: Project,
) -> None:
    dropped = project.package_dir / "config" / "old.py"
    dropped.parent.mkdir(parents=True)
    _ = dropped.write_text("OLD\n", encoding="utf-8")
    prior = LockEntry(files={"src/app/config/old.py": LockedFile(_sha256("OLD\n"), adopted=False)})

    planned = planner.update(_recipe(), prior, force=False)

    assert DeleteFile(dropped, "src/app/config/old.py") in planned.operations


def test_update_keeps_a_dropped_file_that_was_edited(
    planner: RecipePlanner,
    project: Project,
) -> None:
    dropped = project.package_dir / "config" / "old.py"
    dropped.parent.mkdir(parents=True)
    _ = dropped.write_text("EDITED\n", encoding="utf-8")
    prior = LockEntry(files={"src/app/config/old.py": LockedFile(_sha256("OLD\n"), adopted=False)})

    planned = planner.update(_recipe(), prior, force=False)

    assert KeepFile("src/app/config/old.py", "edited") in planned.operations


def test_update_clears_a_block_the_recipe_no_longer_contributes_to(
    planner: RecipePlanner,
    project: Project,
) -> None:
    path = project.project_dir / ".env"
    _ = path.write_text(
        f"# >>> {_PACKAGE}\n# MESSENGER_DSN=\n# <<< {_PACKAGE}\n",
        encoding="utf-8",
    )

    planned = planner.update(_recipe(env={}), LockEntry(), force=False)

    assert RemoveBlock(path, ".env", _PACKAGE) in planned.operations


def test_unconfigure_deletes_an_untouched_file(planner: RecipePlanner, project: Project) -> None:
    path = project.package_dir / _DESTINATION
    path.parent.mkdir(parents=True)
    _ = path.write_text(_RENDERED, encoding="utf-8")
    prior = LockEntry(files={_LOCKED: LockedFile(_sha256(_RENDERED), adopted=False)})

    assert planner.unconfigure(_PACKAGE, prior) == (DeleteFile(path, _LOCKED),)


def test_unconfigure_moves_an_adopted_file_aside(planner: RecipePlanner, project: Project) -> None:
    path = project.package_dir / _DESTINATION
    path.parent.mkdir(parents=True)
    _ = path.write_text("MINE\n", encoding="utf-8")
    prior = LockEntry(files={_LOCKED: LockedFile(_sha256("MINE\n"), adopted=True)})

    moved = path.with_name(f"{path.name}.removed")
    assert planner.unconfigure(_PACKAGE, prior) == (
        MoveFile(path, _LOCKED, moved, f"{_LOCKED}.removed", "adopted"),
    )


def test_unconfigure_moves_an_edited_file_aside(planner: RecipePlanner, project: Project) -> None:
    path = project.package_dir / _DESTINATION
    path.parent.mkdir(parents=True)
    _ = path.write_text("EDITED\n", encoding="utf-8")
    prior = LockEntry(files={_LOCKED: LockedFile(_sha256(_RENDERED), adopted=False)})

    moved = path.with_name(f"{path.name}.removed")
    assert planner.unconfigure(_PACKAGE, prior) == (
        MoveFile(path, _LOCKED, moved, f"{_LOCKED}.removed", "edited"),
    )


def test_unconfigure_never_moves_a_file_over_an_earlier_one(
    planner: RecipePlanner,
    project: Project,
) -> None:
    path = project.package_dir / _DESTINATION
    path.parent.mkdir(parents=True)
    _ = path.write_text("EDITED\n", encoding="utf-8")
    _ = path.with_name(f"{path.name}.removed").write_text("OLDER\n", encoding="utf-8")
    prior = LockEntry(files={_LOCKED: LockedFile(_sha256(_RENDERED), adopted=False)})

    moved = path.with_name(f"{path.name}.removed.1")
    assert planner.unconfigure(_PACKAGE, prior) == (
        MoveFile(path, _LOCKED, moved, f"{_LOCKED}.removed.1", "edited"),
    )


def test_an_update_keeps_a_dropped_file_where_it_is(
    planner: RecipePlanner,
    project: Project,
) -> None:
    path = project.package_dir / _DESTINATION
    path.parent.mkdir(parents=True)
    _ = path.write_text("MINE\n", encoding="utf-8")
    prior = LockEntry(files={_LOCKED: LockedFile(_sha256("MINE\n"), adopted=True)})

    planned = planner.update(_recipe(files={}), prior, force=False)

    assert KeepFile(_LOCKED, "adopted") in planned.operations


def test_unconfigure_says_nothing_about_a_file_already_gone(planner: RecipePlanner) -> None:
    prior = LockEntry(files={_LOCKED: LockedFile(_sha256(_RENDERED), adopted=False)})

    assert planner.unconfigure(_PACKAGE, prior) == ()


def test_unconfigure_removes_the_blocks_the_recipe_wrote(
    planner: RecipePlanner,
    project: Project,
) -> None:
    env = project.project_dir / ".env"
    ignore = project.project_dir / ".gitignore"
    for path in (env, ignore):
        _ = path.write_text(f"# >>> {_PACKAGE}\nLINE\n# <<< {_PACKAGE}\n", encoding="utf-8")

    assert planner.unconfigure(_PACKAGE, LockEntry()) == (
        RemoveBlock(env, ".env", _PACKAGE),
        RemoveBlock(ignore, ".gitignore", _PACKAGE),
    )


def test_unconfigure_leaves_a_file_without_a_block_alone(planner: RecipePlanner) -> None:
    assert planner.unconfigure(_PACKAGE, LockEntry()) == ()


def test_planning_writes_nothing(planner: RecipePlanner, project: Project) -> None:
    before = sorted(path.name for path in project.project_dir.rglob("*"))

    _ = planner.configure(_recipe(env={"MESSENGER_DSN": ""}, gitignore=("/var",)))

    assert sorted(path.name for path in project.project_dir.rglob("*")) == before

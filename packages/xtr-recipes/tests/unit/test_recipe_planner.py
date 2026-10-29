from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import pytest

from tests.support import build_project
from xtr_recipes.key_pair_config import KeyPairConfig
from xtr_recipes.marked_block_editor import MarkedBlockEditor
from xtr_recipes.notes_config import NotesConfig
from xtr_recipes.operation.delete_file import DeleteFile
from xtr_recipes.operation.keep_file import KeepFile
from xtr_recipes.operation.mint_key import MintKey
from xtr_recipes.operation.move_file import MoveFile
from xtr_recipes.operation.notes import Notes
from xtr_recipes.operation.put_block import PutBlock
from xtr_recipes.operation.put_compose_blocks import PutComposeBlocks
from xtr_recipes.operation.remove_block import RemoveBlock
from xtr_recipes.operation.write_file import WriteFile
from xtr_recipes.operation.write_new_file import WriteNewFile
from xtr_recipes.recipe_config import RecipeConfig
from xtr_recipes.recipe_loader import Recipe
from xtr_recipes.recipe_lock import LockedFile, LockEntry
from xtr_recipes.recipe_planner import RecipePlanner
from xtr_recipes.secret_config import SecretConfig

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


GENERATED_SECRET = "%generate(secret)%"


def _secrets(env: Mapping[str, str]) -> dict[str, SecretConfig]:
    """Read the generators in ``env`` the way a manifest's are read."""
    parsed = {name: SecretConfig.parse(_PACKAGE, name, value) for name, value in env.items()}
    return {name: secret for name, secret in parsed.items() if secret is not None}


def _recipe(
    files: Mapping[str, str] | None = None,
    env: Mapping[str, str] | None = None,
    gitignore: tuple[str, ...] = (),
    notes: NotesConfig | None = None,
    compose: Mapping[str, Mapping[str, tuple[str, ...]]] | None = None,
) -> Recipe:
    return Recipe(
        distribution=_PACKAGE,
        config=RecipeConfig(
            files={_DESTINATION: _TEMPLATE} if files is None else files,
            env=env or {},
            secrets=_secrets(env or {}),
            gitignore=gitignore,
            compose=compose or {},
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


def test_configure_renders_a_nested_application_by_its_dotted_name(tmp_path: Path) -> None:
    nested = build_project(tmp_path, app="acme.shop", dependencies=[_PACKAGE])

    planned = RecipePlanner(nested, MarkedBlockEditor()).configure(_recipe())

    assert planned.files == {
        "src/acme/shop/config/messenger.py": LockedFile(
            _sha256("MESSENGER = acme.shop\n"), adopted=False
        ),
    }


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


def test_a_destination_deeper_in_config_creates_every_package_on_the_way(
    planner: RecipePlanner,
) -> None:
    planned = planner.configure(_recipe(files={"config/routes/books.py": _TEMPLATE}))

    assert [step.render() for step in planned.operations] == [
        (f"  write {_CONFIG_INIT}",),
        ("  write src/app/config/routes/__init__.py",),
        ("  write src/app/config/routes/books.py",),
    ]
    assert "src/app/config/routes/__init__.py" not in planned.files


def test_a_nested_config_package_is_created_once_per_run(planner: RecipePlanner) -> None:
    _ = planner.configure(_recipe(files={"config/routes/books.py": _TEMPLATE}))
    second = planner.configure(_recipe(files={"config/routes/shop.py": _TEMPLATE}))

    assert [step.render() for step in second.operations] == [
        ("  write src/app/config/routes/shop.py",),
    ]


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
        f"###> {_PACKAGE} ###\n# MESSENGER_DSN=\n###< {_PACKAGE} ###\n",
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
        _ = path.write_text(f"###> {_PACKAGE} ###\nLINE\n###< {_PACKAGE} ###\n", encoding="utf-8")

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


_KEY = "secrets/server.pem"
_PASSPHRASE = "SERVER_KEY_PASSPHRASE"


def _keyed_recipe(env: Mapping[str, str] | None = None) -> Recipe:
    chosen = {_PASSPHRASE: GENERATED_SECRET} if env is None else env
    return Recipe(
        distribution=_PACKAGE,
        config=RecipeConfig(
            env=chosen,
            secrets=_secrets(chosen),
            keys={_KEY: KeyPairConfig("RS256", _PASSPHRASE)},
        ),
        templates={},
        recipe_hash="hash",
    )


def _block(planned_operations: tuple[object, ...]) -> PutBlock:
    return next(step for step in planned_operations if isinstance(step, PutBlock))


def test_a_generated_secret_is_written_in_place_of_its_placeholder(
    planner: RecipePlanner,
) -> None:
    planned = planner.configure(_recipe(files={}, env={"SECRET": GENERATED_SECRET}))

    (line,) = _block(planned.operations).lines
    assert line.startswith("SECRET=")
    assert GENERATED_SECRET not in line
    assert len(line.removeprefix("SECRET=")) == 43


def test_a_configured_generator_writes_the_secret_it_describes(planner: RecipePlanner) -> None:
    spelled = "%generate(secret, bytes=16, encoding=hex, prefix=key_)%"

    planned = planner.configure(_recipe(files={}, env={"SECRET": spelled}))

    (line,) = _block(planned.operations).lines
    value = line.removeprefix("SECRET=")
    assert value.startswith("key_")
    assert len(value.removeprefix("key_")) == 32
    assert int(value.removeprefix("key_"), 16) >= 0


def test_each_plan_generates_a_new_secret(planner: RecipePlanner, project: Project) -> None:
    first = planner.configure(_recipe(files={}, env={"SECRET": GENERATED_SECRET}))
    second = RecipePlanner(project, MarkedBlockEditor()).configure(
        _recipe(files={}, env={"SECRET": GENERATED_SECRET})
    )

    assert _block(first.operations).lines != _block(second.operations).lines


def test_a_secret_already_in_the_block_is_kept(planner: RecipePlanner, project: Project) -> None:
    env = project.project_dir / ".env"
    _ = env.write_text(f"###> {_PACKAGE} ###\nSECRET=mine\n###< {_PACKAGE} ###\n", encoding="utf-8")

    planned = planner.configure(_recipe(files={}, env={"SECRET": GENERATED_SECRET}))

    assert all(not isinstance(step, PutBlock) for step in planned.operations)


def test_a_missing_key_is_minted_with_the_secret_the_block_writes(
    planner: RecipePlanner,
    project: Project,
) -> None:
    planned = planner.configure(_keyed_recipe())

    (line,) = _block(planned.operations).lines
    mint = next(step for step in planned.operations if isinstance(step, MintKey))
    assert mint == MintKey(
        (project.project_dir / _KEY).resolve(),
        _KEY,
        "RS256",
        line.removeprefix(f"{_PASSPHRASE}="),
    )


def test_a_key_is_minted_with_a_passphrase_already_set_outside_the_block(
    planner: RecipePlanner,
    project: Project,
) -> None:
    _ = (project.project_dir / ".env").write_text(f"{_PASSPHRASE}='chosen'\n", encoding="utf-8")

    planned = planner.configure(_keyed_recipe())

    mint = next(step for step in planned.operations if isinstance(step, MintKey))
    assert mint.passphrase == "chosen"


def test_a_key_already_on_disk_is_kept_and_given_no_new_passphrase(
    planner: RecipePlanner,
    project: Project,
) -> None:
    key = project.project_dir / _KEY
    key.parent.mkdir()
    _ = key.write_text("KEY\n", encoding="utf-8")

    planned = planner.configure(_keyed_recipe())

    assert KeepFile(_KEY, "in place") in planned.operations
    assert all(not isinstance(step, MintKey) for step in planned.operations)
    assert _block(planned.operations).lines == (f"# {_PASSPHRASE}=",)


def test_a_key_needs_no_passphrase(planner: RecipePlanner, project: Project) -> None:
    recipe = Recipe(
        distribution=_PACKAGE,
        config=RecipeConfig(keys={_KEY: KeyPairConfig("EdDSA")}),
        templates={},
        recipe_hash="hash",
    )

    planned = planner.configure(recipe)

    assert planned.operations == (
        MintKey((project.project_dir / _KEY).resolve(), _KEY, "EdDSA", None),
    )


def test_a_minted_key_is_not_recorded_in_the_lock(planner: RecipePlanner) -> None:
    planned = planner.configure(_keyed_recipe())

    assert planned.files == {}
    assert planned.env == (_PASSPHRASE,)


_PATH_ENV = "SERVER_KEY_PATH"
_PATH_DEFAULT = f"%kernel.project_dir%/{_KEY}"


def _pathed_recipe() -> Recipe:
    env = {_PATH_ENV: _PATH_DEFAULT, _PASSPHRASE: GENERATED_SECRET}
    return Recipe(
        distribution=_PACKAGE,
        config=RecipeConfig(
            env=env,
            secrets=_secrets(env),
            keys={_KEY: KeyPairConfig("RS256", _PASSPHRASE, _PATH_ENV)},
        ),
        templates={},
        recipe_hash="hash",
    )


def test_a_key_the_project_reads_from_elsewhere_is_not_minted(
    planner: RecipePlanner,
    project: Project,
) -> None:
    env = project.project_dir / ".env"
    _ = env.write_text(f"{_PATH_ENV}=%kernel.project_dir%/secrets/mine.pem\n", encoding="utf-8")

    planned = planner.configure(_pathed_recipe())

    assert all(not isinstance(step, MintKey | KeepFile) for step in planned.operations)
    assert _block(planned.operations).lines == (f"# {_PASSPHRASE}=",)


def test_a_key_whose_path_variable_keeps_its_default_is_minted(
    planner: RecipePlanner,
) -> None:
    planned = planner.configure(_pathed_recipe())

    assert any(isinstance(step, MintKey) for step in planned.operations)


_PACKAGED = "config/packages/messenger.py"
_PACKAGED_LOCKED = "src/app/config/packages/messenger.py"


def test_a_file_the_recipe_wrote_in_the_earlier_layout_is_carried_over(
    planner: RecipePlanner,
    project: Project,
) -> None:
    earlier = _existing(project, _RENDERED)
    prior = LockEntry(files={_LOCKED: LockedFile(_sha256(_RENDERED), adopted=False)})

    planned = planner.update(_recipe(files={_PACKAGED: _TEMPLATE}), prior, force=False)

    moved = project.package_dir / _PACKAGED
    assert MoveFile(earlier, _LOCKED, moved, _PACKAGED_LOCKED, "relocated") in planned.operations
    assert planned.files == {_PACKAGED_LOCKED: LockedFile(_sha256(_RENDERED), adopted=False)}
    assert all(not isinstance(step, DeleteFile) for step in planned.operations)


def test_a_carried_file_untouched_since_takes_the_new_content(
    planner: RecipePlanner,
    project: Project,
) -> None:
    _ = _existing(project, "OLD\n")
    prior = LockEntry(files={_LOCKED: LockedFile(_sha256("OLD\n"), adopted=False)})

    planned = planner.update(_recipe(files={_PACKAGED: _TEMPLATE}), prior, force=False)

    moved = project.package_dir / _PACKAGED
    assert WriteFile(moved, _PACKAGED_LOCKED, _RENDERED) in planned.operations


def test_a_carried_file_the_owner_edited_keeps_the_edit(
    planner: RecipePlanner,
    project: Project,
) -> None:
    _ = _existing(project, "MINE\n")
    prior = LockEntry(files={_LOCKED: LockedFile(_sha256(_RENDERED), adopted=False)})

    planned = planner.update(_recipe(files={_PACKAGED: _TEMPLATE}), prior, force=False)

    moved = project.package_dir / _PACKAGED
    assert WriteNewFile(moved, _PACKAGED_LOCKED, _RENDERED) in planned.operations
    assert planned.files[_PACKAGED_LOCKED] == LockedFile(_sha256(_RENDERED), adopted=False)


def test_an_adopted_file_in_the_earlier_layout_stays_where_it_is(
    planner: RecipePlanner,
    project: Project,
) -> None:
    _ = _existing(project, "MINE\n")
    prior = LockEntry(files={_LOCKED: LockedFile(_sha256("MINE\n"), adopted=True)})

    planned = planner.update(_recipe(files={_PACKAGED: _TEMPLATE}), prior, force=False)

    assert KeepFile(_LOCKED, "adopted") in planned.operations
    assert planned.files == {_LOCKED: LockedFile(_sha256("MINE\n"), adopted=True)}
    moved = project.package_dir / _PACKAGED
    assert all(not isinstance(step, MoveFile) for step in planned.operations)
    assert all(
        not (isinstance(step, WriteFile) and step.path == moved) for step in planned.operations
    )


_SERVICES = {"compose.yaml": {"services": ("  broker:",)}}
_COMPOSE_BLOCK = f"services:\n###> {_PACKAGE} ###\n  broker:\n###< {_PACKAGE} ###\n"


def test_configure_writes_the_compose_blocks(planner: RecipePlanner, project: Project) -> None:
    planned = planner.configure(_recipe(files={}, compose=_SERVICES))

    path = project.project_dir.resolve() / "compose.yaml"
    assert planned.operations == (
        PutComposeBlocks(path, "compose.yaml", _PACKAGE, _SERVICES["compose.yaml"]),
    )


def test_the_compose_file_the_project_already_keeps_is_written_into(
    planner: RecipePlanner, project: Project
) -> None:
    _ = (project.project_dir / "docker-compose.yml").write_text("services:\n", encoding="utf-8")

    planned = planner.configure(_recipe(files={}, compose=_SERVICES))

    assert [step.render() for step in planned.operations] == [("  write docker-compose.yml",)]


def test_compose_blocks_already_in_place_plan_nothing(
    planner: RecipePlanner, project: Project
) -> None:
    _ = (project.project_dir / "compose.yaml").write_text(_COMPOSE_BLOCK, encoding="utf-8")

    assert planner.configure(_recipe(files={}, compose=_SERVICES)).operations == ()


def test_a_compose_file_without_the_packages_blocks_is_not_touched(
    planner: RecipePlanner, project: Project
) -> None:
    # Not in the editor's canonical form: clearing nothing must not rewrite it anyway.
    _ = (project.project_dir / "compose.yaml").write_text("services:\n\n\n", encoding="utf-8")

    assert planner.configure(_recipe(files={})).operations == ()


def test_unconfigure_clears_the_compose_blocks(planner: RecipePlanner, project: Project) -> None:
    _ = (project.project_dir / "compose.yaml").write_text(_COMPOSE_BLOCK, encoding="utf-8")

    path = project.project_dir.resolve() / "compose.yaml"
    assert planner.unconfigure(_PACKAGE, LockEntry()) == (
        PutComposeBlocks(path, "compose.yaml", _PACKAGE, {}),
    )


def test_configuring_adopts_a_file_in_the_earlier_layout_instead_of_writing_beside_it(
    planner: RecipePlanner,
    project: Project,
) -> None:
    _ = _existing(project, "MINE\n")

    planned = planner.configure(_recipe(files={_PACKAGED: _TEMPLATE}))

    assert KeepFile(_LOCKED, "adopted") in planned.operations
    assert planned.files == {_LOCKED: LockedFile(_sha256("MINE\n"), adopted=True)}
    assert not (project.package_dir / _PACKAGED).exists()

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, final

import pytest
from xtr_dependency_injection import Bundle, as_bundle, required_bundle

from tests.support import FakeRecipeSource, build_project, recipe_content
from xtr_recipes.bundle_requirements import BundleRequirements
from xtr_recipes.exception import BundlesNotEditableError, RecipeNotInstalledError
from xtr_recipes.project import Project
from xtr_recipes.recipe_lock import LockedFile, LockEntry, RecipeLock
from xtr_recipes.sync_options import SyncOptions
from xtr_recipes.synchronizer import Synchronizer

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

    from xtr_dependency_injection.bundle.bundle import AnyBundle


@final
@as_bundle("sync_clock")
class ClockBundle(Bundle):
    pass


@final
@required_bundle(ClockBundle)
@as_bundle("sync_logging")
class LoggingBundle(Bundle):
    pass


@final
@as_bundle("sync_messenger")
class MessengerBundle(Bundle):
    pass


@final
@as_bundle("sync_own")
class OwnBundle(Bundle):
    pass


_MESSENGER = "xtr-messenger"
_CLOCK = "xtr-clock"
_LOGGING = "xtr-logging"
_MESSENGER_TARGET = "xtr_messenger.bundle:MessengerBundle"
_CLOCK_TARGET = "xtr_clock.bundle:ClockBundle"
_LOGGING_TARGET = "xtr_logging.bundle:LoggingBundle"
_OWN_TARGET = "shared.bundle:OwnBundle"
_KNOWN: Mapping[str, type[AnyBundle]] = {
    _MESSENGER_TARGET: MessengerBundle,
    _CLOCK_TARGET: ClockBundle,
    _LOGGING_TARGET: LoggingBundle,
    _OWN_TARGET: OwnBundle,
}

_TEMPLATE = "files/config/messenger.py.tmpl"
_BODY = "MESSENGER = ${app}\n"
_RENDERED = "MESSENGER = app\n"
_CONFIG = "src/app/config/messenger.py"
_CONFIG_INIT = "src/app/config/__init__.py"
_CONFIG_INIT_BODY = (
    '"""Configuration modules."""\n\nfrom __future__ import annotations\n\n'
    "__all__: list[str] = []\n"
)
_BUNDLES = "src/app/bundles.py"
_DEFAULT_DOCSTRING = "The root bundles, each mapped to the environments it is active in."
_MESSENGER_BUNDLES = (
    f'"""{_DEFAULT_DOCSTRING}"""\n'
    "\n"
    "from __future__ import annotations\n"
    "\n"
    "from xtr_messenger.bundle import MessengerBundle\n"
    "\n"
    '__all__ = ["BUNDLES"]\n'
    "\n"
    "BUNDLES = {\n"
    '    MessengerBundle: {"all": True},\n'
    "}\n"
)
_OWN_BUNDLES = (
    f'"""{_DEFAULT_DOCSTRING}"""\n'
    "\n"
    "from __future__ import annotations\n"
    "\n"
    "from xtr_clock.bundle import ClockBundle\n"
    "\n"
    "from shared.bundle import OwnBundle\n"
    "\n"
    '__all__ = ["BUNDLES"]\n'
    "\n"
    "BUNDLES = {\n"
    '    ClockBundle: {"all": True},\n'
    '    OwnBundle: {"all": True},\n'
    "}\n"
)

_MESSENGER_MANIFEST = f"""\
[bundles]
"{_MESSENGER_TARGET}" = {{ all = true }}

[files]
"config/messenger.py" = "{_TEMPLATE}"

[env]
MESSENGER_DSN = ""

[gitignore]
lines = ["/var/messenger"]

[notes]
check = ["<script> debug:bundles"]
"""

_CLOCK_MANIFEST = f'[bundles]\n"{_CLOCK_TARGET}" = {{ all = true }}\n'
_LOGGING_MANIFEST = f'[bundles]\n"{_LOGGING_TARGET}" = {{ all = true }}\n'
_OWN_MANIFEST = f'[bundles]\n"{_OWN_TARGET}" = {{ all = true }}\n'


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _loader(known: Mapping[str, type[AnyBundle]]) -> Callable[[str], type[AnyBundle] | None]:
    def load(target: str) -> type[AnyBundle] | None:
        return known.get(target)

    return load


def _synchronizer(
    project: Project,
    manifests: Mapping[str, str],
    known: Mapping[str, type[AnyBundle]] | None = None,
) -> Synchronizer:
    source = FakeRecipeSource(
        {name: recipe_content(manifest, {_TEMPLATE: _BODY}) for name, manifest in manifests.items()}
    )
    resolved = _KNOWN if known is None else known
    return Synchronizer(project, source, BundleRequirements(_loader(resolved)))


def _messenger_project(directory: Path) -> Project:
    return build_project(directory, dependencies=[_MESSENGER])


def _bare_project(directory: Path) -> Project:
    return build_project(directory, dependencies=[])


def _snapshot(directory: Path) -> dict[str, str]:
    return {
        str(path.relative_to(directory)): path.read_text(encoding="utf-8")
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def _configured(directory: Path) -> Synchronizer:
    """Apply the messenger recipe to a fresh project, and return the synchronizer."""
    synchronizer = _synchronizer(_messenger_project(directory), {_MESSENGER: _MESSENGER_MANIFEST})
    synchronizer.apply(synchronizer.plan())
    return synchronizer


def _undoing(directory: Path) -> Synchronizer:
    """A synchronizer for the same project with the dependency, and its recipe, gone."""
    return _synchronizer(_bare_project(directory), {})


def _lock(directory: Path) -> RecipeLock:
    return RecipeLock.load(directory)


def _entry(directory: Path, package: str) -> LockEntry:
    return _lock(directory).entries[package]


def _read(directory: Path, name: str) -> str:
    return (directory / name).read_text(encoding="utf-8")


def test_a_fresh_sync_plans_every_step_in_order(tmp_path: Path) -> None:
    project = _messenger_project(tmp_path)

    plan = _synchronizer(project, {_MESSENGER: _MESSENGER_MANIFEST}).plan()

    assert plan.render() == (
        f"configure {_MESSENGER}",
        f"  write {_CONFIG_INIT}",
        f"  write {_CONFIG}",
        "  write .env",
        "  write .gitignore",
        "  bundle MessengerBundle listed",
        "  check:",
        "    - app debug:bundles",
        f"write {_BUNDLES}",
        "write xtr.lock",
    )


def test_a_fresh_sync_has_changes(tmp_path: Path) -> None:
    project = _messenger_project(tmp_path)

    assert _synchronizer(project, {_MESSENGER: _MESSENGER_MANIFEST}).plan().has_changes


def test_planning_writes_nothing(tmp_path: Path) -> None:
    project = _messenger_project(tmp_path)
    before = _snapshot(tmp_path)

    _ = _synchronizer(project, {_MESSENGER: _MESSENGER_MANIFEST}).plan()

    assert _snapshot(tmp_path) == before


def test_applying_writes_the_rendered_config_file(tmp_path: Path) -> None:
    _ = _configured(tmp_path)

    assert _read(tmp_path, _CONFIG) == _RENDERED


def test_applying_writes_the_config_package(tmp_path: Path) -> None:
    _ = _configured(tmp_path)

    assert _read(tmp_path, _CONFIG_INIT) == _CONFIG_INIT_BODY


def test_applying_writes_the_env_block_with_a_commented_default(tmp_path: Path) -> None:
    _ = _configured(tmp_path)

    assert _read(tmp_path, ".env") == (
        f"# >>> {_MESSENGER}\n# MESSENGER_DSN=\n# <<< {_MESSENGER}\n"
    )


def test_applying_writes_the_gitignore_block(tmp_path: Path) -> None:
    _ = _configured(tmp_path)

    assert _read(tmp_path, ".gitignore") == (
        f"# >>> {_MESSENGER}\n/var/messenger\n# <<< {_MESSENGER}\n"
    )


def test_applying_writes_the_bundle_list(tmp_path: Path) -> None:
    _ = _configured(tmp_path)

    assert _read(tmp_path, _BUNDLES) == _MESSENGER_BUNDLES


def test_applying_records_what_it_did_in_the_lock(tmp_path: Path) -> None:
    _ = _configured(tmp_path)

    entry = _entry(tmp_path, _MESSENGER)

    assert entry.bundles == {_MESSENGER_TARGET: "listed"}
    assert entry.env == ("MESSENGER_DSN",)
    assert entry.gitignore == ("/var/messenger",)
    assert entry.files == {_CONFIG: LockedFile(_sha256(_RENDERED), adopted=False)}


def test_a_second_plan_finds_nothing_to_do(tmp_path: Path) -> None:
    synchronizer = _configured(tmp_path)

    again = synchronizer.plan()

    assert again.render() == ()
    assert not again.has_changes


def test_applying_twice_leaves_the_project_the_same(tmp_path: Path) -> None:
    synchronizer = _configured(tmp_path)
    after_first = _snapshot(tmp_path)

    synchronizer.apply(synchronizer.plan())

    assert _snapshot(tmp_path) == after_first


def test_an_existing_project_is_adopted_rather_than_rewritten(tmp_path: Path) -> None:
    project = _messenger_project(tmp_path)
    config = tmp_path / _CONFIG
    config.parent.mkdir(parents=True)
    _ = config.write_text("MINE\n", encoding="utf-8")
    _ = (tmp_path / _CONFIG_INIT).write_text(_CONFIG_INIT_BODY, encoding="utf-8")
    _ = (tmp_path / _BUNDLES).write_text(_MESSENGER_BUNDLES, encoding="utf-8")
    _ = (tmp_path / ".env").write_text("MESSENGER_DSN=amqp://mine\n", encoding="utf-8")
    _ = (tmp_path / ".gitignore").write_text("/var/messenger\n", encoding="utf-8")
    before = _snapshot(tmp_path)
    synchronizer = _synchronizer(project, {_MESSENGER: _MESSENGER_MANIFEST})

    plan = synchronizer.plan()
    synchronizer.apply(plan)

    assert plan.render() == (
        f"configure {_MESSENGER}",
        f"  kept {_CONFIG} (adopted)",
        "  bundle MessengerBundle already listed",
        "  check:",
        "    - app debug:bundles",
        "write xtr.lock",
    )
    assert _snapshot(tmp_path) == {**before, "xtr.lock": _read(tmp_path, "xtr.lock")}


def test_adoption_records_the_file_as_adopted_and_nothing_else(tmp_path: Path) -> None:
    project = _messenger_project(tmp_path)
    config = tmp_path / _CONFIG
    config.parent.mkdir(parents=True)
    _ = config.write_text("MINE\n", encoding="utf-8")
    _ = (tmp_path / ".env").write_text("MESSENGER_DSN=amqp://mine\n", encoding="utf-8")
    synchronizer = _synchronizer(project, {_MESSENGER: _MESSENGER_MANIFEST})

    synchronizer.apply(synchronizer.plan())

    entry = _entry(tmp_path, _MESSENGER)

    assert entry.files == {_CONFIG: LockedFile(_sha256("MINE\n"), adopted=True)}
    assert entry.env == ()


def test_a_changed_recipe_overwrites_an_untouched_file(tmp_path: Path) -> None:
    project = _messenger_project(tmp_path)
    first = _synchronizer(project, {_MESSENGER: _MESSENGER_MANIFEST})
    first.apply(first.plan())
    moved = _MESSENGER_MANIFEST.replace("MESSENGER = ", "QUEUE = ")
    second = _synchronizer(project, {_MESSENGER: f"{moved}\n# moved\n"})

    plan = second.plan()
    second.apply(plan)

    assert f"update {_MESSENGER}" in plan.render()
    assert f"  write {_CONFIG}" not in plan.render()
    assert _read(tmp_path, _CONFIG) == _RENDERED


def test_a_changed_recipe_rewrites_a_block_whose_lines_moved(tmp_path: Path) -> None:
    project = _messenger_project(tmp_path)
    first = _synchronizer(project, {_MESSENGER: _MESSENGER_MANIFEST})
    first.apply(first.plan())
    moved = _MESSENGER_MANIFEST.replace('["/var/messenger"]', '["/var/queue"]')
    second = _synchronizer(project, {_MESSENGER: moved})

    second.apply(second.plan())

    assert _read(tmp_path, ".gitignore") == f"# >>> {_MESSENGER}\n/var/queue\n# <<< {_MESSENGER}\n"
    assert _entry(tmp_path, _MESSENGER).gitignore == ("/var/queue",)


def test_a_changed_recipe_offers_a_new_file_beside_an_edited_one(tmp_path: Path) -> None:
    synchronizer = _configured(tmp_path)
    _ = (tmp_path / _CONFIG).write_text("EDITED\n", encoding="utf-8")
    locked = _entry(tmp_path, _MESSENGER).files
    changed = _synchronizer(
        _messenger_project(tmp_path),
        {_MESSENGER: f"{_MESSENGER_MANIFEST}\n# moved\n"},
    )

    plan = changed.plan()
    changed.apply(plan)

    assert f"  write {_CONFIG}.new" in plan.render()
    assert _read(tmp_path, _CONFIG) == "EDITED\n"
    assert _read(tmp_path, f"{_CONFIG}.new") == _RENDERED
    assert _entry(tmp_path, _MESSENGER).files == locked
    assert synchronizer is not changed


def test_naming_one_package_with_force_overwrites_an_edited_file(tmp_path: Path) -> None:
    synchronizer = _configured(tmp_path)
    _ = (tmp_path / _CONFIG).write_text("EDITED\n", encoding="utf-8")

    plan = synchronizer.plan(SyncOptions(force=True, only=_MESSENGER))
    synchronizer.apply(plan)

    assert f"  write {_CONFIG}" in plan.render()
    assert _read(tmp_path, _CONFIG) == _RENDERED
    assert _entry(tmp_path, _MESSENGER).files == {
        _CONFIG: LockedFile(_sha256(_RENDERED), adopted=False)
    }


def test_naming_one_package_re_applies_it_even_with_the_same_recipe(tmp_path: Path) -> None:
    synchronizer = _configured(tmp_path)
    (tmp_path / _CONFIG).unlink()

    synchronizer.apply(synchronizer.plan(SyncOptions(only=_MESSENGER)))

    assert _read(tmp_path, _CONFIG) == _RENDERED


def test_naming_one_package_however_it_is_spelled(tmp_path: Path) -> None:
    synchronizer = _configured(tmp_path)

    assert f"update {_MESSENGER}" in synchronizer.plan(SyncOptions(only="XTR_Messenger")).render()


def test_naming_one_package_leaves_the_rest_of_the_lock_alone(tmp_path: Path) -> None:
    project = build_project(tmp_path, dependencies=[_MESSENGER, _LOGGING])
    manifests = {_MESSENGER: _MESSENGER_MANIFEST, _LOGGING: _LOGGING_MANIFEST}
    synchronizer = _synchronizer(project, manifests)
    synchronizer.apply(synchronizer.plan())

    synchronizer.apply(synchronizer.plan(SyncOptions(only=_MESSENGER)))

    assert set(_lock(tmp_path).entries) == {_MESSENGER, _LOGGING}


def test_naming_a_package_with_no_recipe_is_an_error(tmp_path: Path) -> None:
    project = _messenger_project(tmp_path)
    synchronizer = _synchronizer(project, {_MESSENGER: _MESSENGER_MANIFEST})

    with pytest.raises(RecipeNotInstalledError) as error:
        _ = synchronizer.plan(SyncOptions(only="xtr-orm"))

    assert error.value.package == "xtr-orm"


def test_a_recipe_of_a_package_that_is_not_a_dependency_is_ignored(tmp_path: Path) -> None:
    project = _bare_project(tmp_path)

    assert _synchronizer(project, {_MESSENGER: _MESSENGER_MANIFEST}).plan().render() == ()


def test_removing_the_dependency_undoes_the_recipe(tmp_path: Path) -> None:
    _ = _configured(tmp_path)
    undoing = _undoing(tmp_path)

    plan = undoing.plan()
    undoing.apply(plan)

    assert plan.render() == (
        f"unconfigure {_MESSENGER}",
        f"  delete {_CONFIG}",
        "  clear .env",
        "  clear .gitignore",
        "  bundle MessengerBundle removed",
        f"write {_BUNDLES}",
        "write xtr.lock",
    )
    assert not (tmp_path / _CONFIG).exists()
    assert not _read(tmp_path, ".env")
    assert _lock(tmp_path).entries == {}


def test_unconfiguring_removes_the_bundle_from_the_list(tmp_path: Path) -> None:
    _ = _configured(tmp_path)
    undoing = _undoing(tmp_path)

    undoing.apply(undoing.plan())

    assert "MessengerBundle" not in _read(tmp_path, _BUNDLES)


def test_unconfiguring_leaves_the_config_package_alone(tmp_path: Path) -> None:
    _ = _configured(tmp_path)
    undoing = _undoing(tmp_path)

    undoing.apply(undoing.plan())

    assert _read(tmp_path, _CONFIG_INIT) == _CONFIG_INIT_BODY


def test_unconfiguring_moves_an_edited_file_out_of_the_application(tmp_path: Path) -> None:
    _ = _configured(tmp_path)
    _ = (tmp_path / _CONFIG).write_text("EDITED\n", encoding="utf-8")
    undoing = _undoing(tmp_path)

    plan = undoing.plan()
    undoing.apply(plan)

    assert f"  moved {_CONFIG} to {_CONFIG}.removed (edited)" in plan.render()
    assert not (tmp_path / _CONFIG).exists()
    assert _read(tmp_path, f"{_CONFIG}.removed") == "EDITED\n"


def test_unconfiguring_moves_an_adopted_file_out_of_the_application(tmp_path: Path) -> None:
    project = _messenger_project(tmp_path)
    config = tmp_path / _CONFIG
    config.parent.mkdir(parents=True)
    _ = config.write_text("MINE\n", encoding="utf-8")
    first = _synchronizer(project, {_MESSENGER: _MESSENGER_MANIFEST})
    first.apply(first.plan())
    undoing = _undoing(tmp_path)

    plan = undoing.plan()
    undoing.apply(plan)

    assert f"  moved {_CONFIG} to {_CONFIG}.removed (adopted)" in plan.render()
    assert not (tmp_path / _CONFIG).exists()
    assert _read(tmp_path, f"{_CONFIG}.removed") == "MINE\n"


def test_unconfiguring_leaves_an_env_key_the_owner_set(tmp_path: Path) -> None:
    project = _messenger_project(tmp_path)
    _ = (tmp_path / ".env").write_text("MESSENGER_DSN=amqp://mine\n", encoding="utf-8")
    first = _synchronizer(project, {_MESSENGER: _MESSENGER_MANIFEST})
    first.apply(first.plan())
    undoing = _undoing(tmp_path)

    undoing.apply(undoing.plan())

    assert _read(tmp_path, ".env") == "MESSENGER_DSN=amqp://mine\n"


def test_a_bundle_another_one_requires_is_not_listed(tmp_path: Path) -> None:
    project = build_project(tmp_path, dependencies=[_CLOCK, _LOGGING])
    manifests = {_CLOCK: _CLOCK_MANIFEST, _LOGGING: _LOGGING_MANIFEST}
    synchronizer = _synchronizer(project, manifests)

    plan = synchronizer.plan()
    synchronizer.apply(plan)

    assert "  bundle ClockBundle required by another bundle" in plan.render()
    assert "ClockBundle" not in _read(tmp_path, _BUNDLES)
    assert _entry(tmp_path, _CLOCK).bundles == {_CLOCK_TARGET: "required"}


def test_a_bundle_is_listed_once_its_requirer_goes_away(tmp_path: Path) -> None:
    project = build_project(tmp_path, dependencies=[_CLOCK, _LOGGING])
    manifests = {_CLOCK: _CLOCK_MANIFEST, _LOGGING: _LOGGING_MANIFEST}
    first = _synchronizer(project, manifests)
    first.apply(first.plan())
    alone = build_project(tmp_path, dependencies=[_CLOCK])
    second = _synchronizer(alone, {_CLOCK: _CLOCK_MANIFEST})

    second.apply(second.plan())

    assert "ClockBundle" in _read(tmp_path, _BUNDLES)
    assert _entry(tmp_path, _CLOCK).bundles == {_CLOCK_TARGET: "listed"}
    assert set(_lock(tmp_path).entries) == {_CLOCK}


def test_a_recipe_whose_bundle_class_is_absent_is_skipped(tmp_path: Path) -> None:
    project = _messenger_project(tmp_path)
    synchronizer = _synchronizer(project, {_MESSENGER: _MESSENGER_MANIFEST}, known={})

    plan = synchronizer.plan()
    synchronizer.apply(plan)

    assert plan.render() == (
        f"skip {_MESSENGER}",
        f"  bundle MessengerBundle skipped: install {_MESSENGER}[di]",
    )
    assert not plan.has_changes
    assert not (tmp_path / "xtr.lock").exists()
    assert not (tmp_path / _CONFIG).exists()


def test_naming_a_skipped_package_reports_the_skip(tmp_path: Path) -> None:
    project = _messenger_project(tmp_path)
    synchronizer = _synchronizer(project, {_MESSENGER: _MESSENGER_MANIFEST}, known={})

    assert synchronizer.plan(SyncOptions(only=_MESSENGER)).render() == (
        f"skip {_MESSENGER}",
        f"  bundle MessengerBundle skipped: install {_MESSENGER}[di]",
    )


def test_a_survey_sorts_an_installed_recipe_the_lock_has_never_recorded(tmp_path: Path) -> None:
    project = _messenger_project(tmp_path)

    survey = _synchronizer(project, {_MESSENGER: _MESSENGER_MANIFEST}).survey()

    assert tuple(survey.installed) == (_MESSENGER,)
    assert survey.selection.configure == (_MESSENGER,)


def test_a_survey_sorts_an_applied_recipe_as_unchanged(tmp_path: Path) -> None:
    synchronizer = _configured(tmp_path)

    assert synchronizer.survey().selection.unchanged == (_MESSENGER,)


def test_a_survey_reports_a_package_whose_bundle_class_is_absent(tmp_path: Path) -> None:
    project = _messenger_project(tmp_path)

    survey = _synchronizer(project, {_MESSENGER: _MESSENGER_MANIFEST}, known={}).survey()

    assert survey.skipped == {_MESSENGER: (_MESSENGER_TARGET,)}
    assert survey.installed == {}


def test_a_survey_reports_a_locked_package_that_is_gone(tmp_path: Path) -> None:
    _ = _configured(tmp_path)

    assert _undoing(tmp_path).survey().selection.unconfigure == (_MESSENGER,)


def test_surveying_writes_nothing(tmp_path: Path) -> None:
    project = _messenger_project(tmp_path)
    before = _snapshot(tmp_path)

    _ = _synchronizer(project, {_MESSENGER: _MESSENGER_MANIFEST}).survey()

    assert _snapshot(tmp_path) == before


def test_a_bundle_list_it_cannot_rewrite_stops_the_sync(tmp_path: Path) -> None:
    project = _messenger_project(tmp_path)
    _ = (tmp_path / _BUNDLES).write_text("BUNDLES = {**other}\n", encoding="utf-8")
    before = _snapshot(tmp_path)
    synchronizer = _synchronizer(project, {_MESSENGER: _MESSENGER_MANIFEST})

    with pytest.raises(BundlesNotEditableError):
        _ = synchronizer.plan()

    assert _snapshot(tmp_path) == before


def test_an_application_with_nothing_to_list_is_given_no_bundle_file(tmp_path: Path) -> None:
    project = _bare_project(tmp_path)

    _synchronizer(project, {}).plan().apply()

    assert not (tmp_path / _BUNDLES).exists()
    assert not (tmp_path / "xtr.lock").exists()


def test_it_syncs_an_application_laid_out_at_the_project_root(tmp_path: Path) -> None:
    _ = (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname = "app"\ndependencies = ["{_MESSENGER}"]\n',
        encoding="utf-8",
    )
    (tmp_path / "app").mkdir()
    project = Project.load(tmp_path)
    synchronizer = _synchronizer(project, {_MESSENGER: _MESSENGER_MANIFEST})

    synchronizer.apply(synchronizer.plan())

    assert _read(tmp_path, "app/config/messenger.py") == _RENDERED
    assert "from xtr_messenger.bundle import MessengerBundle" in _read(tmp_path, "app/bundles.py")


def test_a_bundle_of_the_applications_own_packages_is_imported_last(tmp_path: Path) -> None:
    project = build_project(tmp_path, dependencies=[_MESSENGER, _CLOCK])
    (tmp_path / "src" / "shared").mkdir()
    manifests = {_MESSENGER: _OWN_MANIFEST, _CLOCK: _CLOCK_MANIFEST}
    synchronizer = _synchronizer(project, manifests)

    synchronizer.apply(synchronizer.plan())

    assert _read(tmp_path, _BUNDLES) == _OWN_BUNDLES


def test_a_configured_package_whose_bundle_stops_loading_is_left_alone(tmp_path: Path) -> None:
    _ = _configured(tmp_path)
    broken = _synchronizer(
        _messenger_project(tmp_path), {_MESSENGER: _MESSENGER_MANIFEST}, known={}
    )

    plan = broken.plan()

    assert not plan.has_changes
    assert _MESSENGER in _lock(tmp_path).entries


@final
@required_bundle(ClockBundle)
@as_bundle("sync_dev_tools")
class DevToolsBundle(Bundle):
    pass


def test_a_bundle_required_only_by_a_bundle_limited_to_some_environments_is_listed(
    tmp_path: Path,
) -> None:
    project = build_project(tmp_path, dependencies=[_CLOCK])
    bundles = tmp_path / _BUNDLES
    dev_only = 'BUNDLES = {DevToolsBundle: {"dev": True}}\n'
    source = f"from tools.bundle import DevToolsBundle\n\n{dev_only}"
    _ = bundles.write_text(source, encoding="utf-8")
    known = {**_KNOWN, "tools.bundle:DevToolsBundle": DevToolsBundle}
    synchronizer = _synchronizer(project, {_CLOCK: _CLOCK_MANIFEST}, known=known)

    synchronizer.apply(synchronizer.plan())

    assert _entry(tmp_path, _CLOCK).bundles == {_CLOCK_TARGET: "listed"}


def test_a_value_set_inside_the_recipes_own_block_survives_a_re_apply(tmp_path: Path) -> None:
    _ = _configured(tmp_path)
    env = tmp_path / ".env"
    _ = env.write_text(
        _read(tmp_path, ".env").replace("# MESSENGER_DSN=", "MESSENGER_DSN=amqp://real"),
        encoding="utf-8",
    )
    synchronizer = _synchronizer(_messenger_project(tmp_path), {_MESSENGER: _MESSENGER_MANIFEST})

    synchronizer.apply(synchronizer.plan(SyncOptions(only=_MESSENGER)))

    assert "MESSENGER_DSN=amqp://real" in _read(tmp_path, ".env")


def test_a_bundle_is_not_listed_while_its_requirer_does_not_load(tmp_path: Path) -> None:
    project = build_project(tmp_path, dependencies=[_LOGGING, _CLOCK])
    manifests = {_LOGGING: _LOGGING_MANIFEST, _CLOCK: _CLOCK_MANIFEST}
    first = _synchronizer(project, manifests)
    first.apply(first.plan())
    before = _snapshot(tmp_path)
    without_logging = {
        target: bundle for target, bundle in _KNOWN.items() if target != _LOGGING_TARGET
    }

    plan = _synchronizer(project, manifests, known=without_logging).plan()

    assert not plan.has_changes
    assert _snapshot(tmp_path) == before

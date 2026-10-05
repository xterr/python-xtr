from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from xtr_recipes.bundle_entry import BundleEntry
from xtr_recipes.bundles_file import BundlesFile
from xtr_recipes.exception import BundlesNotEditableError

_APPLICATION = Path(__file__).resolve().parents[4] / "examples" / "bookshop"
_ITS_BUNDLES = _APPLICATION / "src" / "bookshop" / "bundles.py"
_ITS_PACKAGES = frozenset({"bookshop", "fulltext"})


def _write(tmp_path: Path, source: str) -> Path:
    path = tmp_path / "bundles.py"
    _ = path.write_text(source, encoding="utf-8")
    return path


def _lint(tmp_path: Path, source: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Lint ``source`` as a module of the application, under its own settings."""
    package = tmp_path / "bookshop"
    package.mkdir(exist_ok=True)
    _ = (package / "__init__.py").write_text('"""The application."""\n', encoding="utf-8")
    path = package / "bundles.py"
    _ = path.write_text(source, encoding="utf-8")
    settings = _APPLICATION / "pyproject.toml"
    command = [
        sys.executable,
        "-m",
        "ruff",
        *arguments,
        "--no-cache",
        "--config",
        str(settings),
        str(path),
    ]
    # The application's settings, named outright: the file sits inside this package, whose
    # own settings ruff would otherwise pick. Run from the application so its `src` entry,
    # which decides the first-party imports, resolves. Built from this test's constants.
    return subprocess.run(  # noqa: S603
        command,
        cwd=_APPLICATION,
        capture_output=True,
        text=True,
        check=False,
    )


def test_it_reads_every_entry_an_application_lists() -> None:
    bundles = BundlesFile.read(_ITS_BUNDLES)

    assert [entry.target for entry in bundles.entries] == [
        "xtr_logging.bundle:LoggingBundle",
        "xtr_console.bundle:ConsoleBundle",
        "xtr_messenger.bundle:MessengerBundle",
        "xtr_orm.bundle:OrmBundle",
        "xtr_dotenv.bundle:DotenvBundle",
        "fulltext.bundle:FulltextBundle",
        "xtr_event_dispatcher.bundle:EventDispatcherBundle",
        "xtr_http_kernel.bundle:HttpKernelBundle",
        "xtr_lock.bundle:LockBundle",
        "xtr_cache.bundle:CacheBundle",
        "xtr_scheduler.bundle:SchedulerBundle",
        "xtr_rate_limiter.bundle:RateLimiterBundle",
        "xtr_security_jwt.bundle:JwtBundle",
        "bookshop.dev_tools:DevToolsBundle",
    ]


def test_it_reads_the_flags_of_an_entry_active_in_two_environments() -> None:
    bundles = BundlesFile.read(_ITS_BUNDLES)

    assert bundles.entries[-1].flags == {"dev": True, "test": True}


def test_it_keeps_the_docstring_a_file_already_has() -> None:
    bundles = BundlesFile.read(_ITS_BUNDLES)

    assert bundles.docstring is not None
    assert bundles.docstring.startswith('"""The root bundles,')


def test_an_aliased_import_resolves_to_the_class_it_renames(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        'from a.b import Real as Local\n\nBUNDLES = {Local: {"all": True}}\n',
    )

    assert BundlesFile.read(path).entries == (BundleEntry("a.b:Real", {"all": True}),)


def test_an_annotated_assignment_is_read_like_a_plain_one(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "from a.b import C\n\nBUNDLES: dict[type, dict[str, bool]] = {C: {}}\n",
    )

    assert BundlesFile.read(path).entries == (BundleEntry("a.b:C", {}),)


def test_an_absent_file_reads_as_an_empty_list(tmp_path: Path) -> None:
    bundles = BundlesFile.read(tmp_path / "bundles.py")

    assert bundles.entries == ()
    assert bundles.docstring is None


def test_a_key_bound_by_no_import_is_refused(tmp_path: Path) -> None:
    path = _write(tmp_path, 'BUNDLES = {Mystery: {"all": True}}\n')

    with pytest.raises(BundlesNotEditableError) as refusal:
        _ = BundlesFile.read(path)

    assert "Mystery" in refusal.value.reason
    assert refusal.value.path == path


def test_a_key_that_is_not_even_a_name_is_refused(tmp_path: Path) -> None:
    path = _write(tmp_path, 'from a.b import C\n\nBUNDLES = {**C, "x": {}}\n')

    with pytest.raises(BundlesNotEditableError) as refusal:
        _ = BundlesFile.read(path)

    assert "`**` unpacking" in refusal.value.reason


def test_flags_computed_instead_of_written_are_refused(tmp_path: Path) -> None:
    path = _write(tmp_path, "from a.b import C\n\nBUNDLES = {C: dict(all=True)}\n")

    with pytest.raises(BundlesNotEditableError) as refusal:
        _ = BundlesFile.read(path)

    assert "not literal values" in refusal.value.reason


def test_flags_that_are_not_true_or_false_are_refused(tmp_path: Path) -> None:
    path = _write(tmp_path, 'from a.b import C\n\nBUNDLES = {C: {"all": 1}}\n')

    with pytest.raises(BundlesNotEditableError) as refusal:
        _ = BundlesFile.read(path)

    assert "true or false" in refusal.value.reason


def test_a_mapping_built_by_a_call_is_refused(tmp_path: Path) -> None:
    path = _write(tmp_path, "from a.b import C\n\nBUNDLES = dict.fromkeys([C], {})\n")

    with pytest.raises(BundlesNotEditableError) as refusal:
        _ = BundlesFile.read(path)

    assert "not written as a dict literal" in refusal.value.reason


def test_two_mappings_are_refused(tmp_path: Path) -> None:
    path = _write(tmp_path, "from a.b import C\n\nBUNDLES = {}\nBUNDLES = {C: {}}\n")

    with pytest.raises(BundlesNotEditableError) as refusal:
        _ = BundlesFile.read(path)

    assert "2 module-level BUNDLES assignments" in refusal.value.reason


def test_no_mapping_at_all_is_refused(tmp_path: Path) -> None:
    path = _write(tmp_path, '"""Nothing to read here."""\n')

    with pytest.raises(BundlesNotEditableError) as refusal:
        _ = BundlesFile.read(path)

    assert "0 module-level BUNDLES assignments" in refusal.value.reason


def test_a_file_that_does_not_parse_is_refused(tmp_path: Path) -> None:
    path = _write(tmp_path, "BUNDLES = {\n")

    with pytest.raises(BundlesNotEditableError) as refusal:
        _ = BundlesFile.read(path)

    assert "does not parse" in refusal.value.reason


def test_adding_appends_after_what_is_already_listed() -> None:
    bundles = BundlesFile(entries=(BundleEntry("a.b:First", {"all": True}),))

    added = bundles.adding([BundleEntry("c.d:Second", {"dev": True})])

    assert added.entries == (
        BundleEntry("a.b:First", {"all": True}),
        BundleEntry("c.d:Second", {"dev": True}),
    )


def test_adding_a_target_already_listed_changes_nothing() -> None:
    bundles = BundlesFile(entries=(BundleEntry("a.b:First", {"all": True}),))

    added = bundles.adding([BundleEntry("a.b:First", {"prod": False})])

    assert added.entries == bundles.entries


def test_removing_drops_only_the_targets_named() -> None:
    bundles = BundlesFile(
        entries=(BundleEntry("a.b:First", {}), BundleEntry("c.d:Second", {})),
    )

    assert bundles.removing(["a.b:First"]).entries == (BundleEntry("c.d:Second", {}),)


def test_with_entries_replaces_the_whole_list() -> None:
    bundles = BundlesFile(entries=(BundleEntry("a.b:First", {}),))

    assert bundles.with_entries([BundleEntry("c.d:Second", {})]).entries == (
        BundleEntry("c.d:Second", {}),
    )


def test_render_imports_the_applications_own_modules_in_the_second_block() -> None:
    bundles = BundlesFile(
        entries=(
            BundleEntry("app.dev_tools:DevToolsBundle", {"dev": True}),
            BundleEntry("xtr_logging.bundle:LoggingBundle", {"all": True}),
        ),
    )

    assert bundles.render(first_party={"app"}) == (
        '"""The root bundles, each mapped to the environments it is active in."""\n'
        "\n"
        "from __future__ import annotations\n"
        "\n"
        "from xtr_logging.bundle import LoggingBundle\n"
        "\n"
        "from app.dev_tools import DevToolsBundle\n"
        "\n"
        '__all__ = ["BUNDLES"]\n'
        "\n"
        "BUNDLES = {\n"
        '    DevToolsBundle: {"dev": True},\n'
        '    LoggingBundle: {"all": True},\n'
        "}\n"
    )


def test_render_writes_an_empty_mapping_for_an_empty_list() -> None:
    assert BundlesFile().render(first_party=()) == (
        '"""The root bundles, each mapped to the environments it is active in."""\n'
        "\n"
        "from __future__ import annotations\n"
        "\n"
        '__all__ = ["BUNDLES"]\n'
        "\n"
        "BUNDLES = {}\n"
    )


def test_render_round_trips_through_read(tmp_path: Path) -> None:
    bundles = BundlesFile.read(_ITS_BUNDLES)

    path = _write(tmp_path, bundles.render(_ITS_PACKAGES))

    assert BundlesFile.read(path).entries == bundles.entries


def test_render_keeps_the_docstring_it_round_trips(tmp_path: Path) -> None:
    bundles = BundlesFile.read(_ITS_BUNDLES)

    path = _write(tmp_path, bundles.render(_ITS_PACKAGES))

    assert BundlesFile.read(path).docstring == bundles.docstring


def test_a_class_name_coming_from_two_modules_is_refused() -> None:
    bundles = BundlesFile(
        entries=(BundleEntry("a.b:Bundle", {}), BundleEntry("c.d:Bundle", {})),
    )

    with pytest.raises(BundlesNotEditableError) as refusal:
        _ = bundles.render(first_party=())

    assert refusal.value.entries == ("a.b:Bundle", "c.d:Bundle")


def test_write_creates_a_file_that_is_not_there_yet(tmp_path: Path) -> None:
    path = tmp_path / "src" / "app" / "bundles.py"

    changed = BundlesFile().write(path, first_party=())

    assert changed
    assert BundlesFile.read(path).entries == ()


def test_write_leaves_a_file_that_already_says_this_untouched(tmp_path: Path) -> None:
    path = tmp_path / "bundles.py"
    bundles = BundlesFile(entries=(BundleEntry("a.b:C", {"all": True}),))
    _ = bundles.write(path, first_party=())
    written_at = path.stat().st_mtime_ns

    changed = bundles.write(path, first_party=())

    assert not changed
    assert path.stat().st_mtime_ns == written_at


def test_write_rewrites_a_file_whose_entries_changed(tmp_path: Path) -> None:
    path = tmp_path / "bundles.py"
    bundles = BundlesFile(entries=(BundleEntry("a.b:C", {"all": True}),))
    _ = bundles.write(path, first_party=())

    changed = bundles.adding([BundleEntry("d.e:F", {"all": True})]).write(path, first_party=())

    assert changed
    assert len(BundlesFile.read(path).entries) == 2


def test_what_it_renders_passes_the_applications_own_check(tmp_path: Path) -> None:
    rendered = BundlesFile.read(_ITS_BUNDLES).render(_ITS_PACKAGES)

    checked = _lint(tmp_path, rendered, "check")

    assert checked.returncode == 0, checked.stdout + checked.stderr


def test_what_it_renders_is_already_formatted_the_applications_way(tmp_path: Path) -> None:
    rendered = BundlesFile.read(_ITS_BUNDLES).render(_ITS_PACKAGES)

    formatted = _lint(tmp_path, rendered, "format", "--check")

    assert formatted.returncode == 0, formatted.stdout + formatted.stderr


def test_it_refuses_a_file_holding_code_it_would_not_write_back(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        'from a.bundle import ABundle\n\nDEBUG = True\n\nBUNDLES = {ABundle: {"all": True}}\n',
    )

    with pytest.raises(BundlesNotEditableError):
        _ = BundlesFile.read(path)


def test_it_writes_a_docstring_back_exactly_as_it_was_spelled(tmp_path: Path) -> None:
    source = (
        'r"""Bundles, \\n kept as written."""\n\nfrom __future__ import annotations\n\n'
        'from a.bundle import ABundle\n\n__all__ = ["BUNDLES"]\n\n'
        'BUNDLES = {\n    ABundle: {"all": True},\n}\n'
    )
    path = _write(tmp_path, source)

    assert BundlesFile.read(path).render(first_party=()) == source

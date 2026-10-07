"""The release script keeps every package, the workspace and every doc on one version."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from types import ModuleType

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "release.py"


def _load() -> ModuleType:
    found = importlib.util.spec_from_file_location("release", _SCRIPT)
    assert found is not None
    assert found.loader is not None
    module = importlib.util.module_from_spec(found)
    sys.modules["release"] = module
    found.loader.exec_module(module)
    return module


release = _load()


def _manifest(name: str, version: str, requirements: list[str]) -> str:
    listed = "".join(f"    {requirement}\n" for requirement in requirements)
    return f'[project]\nname = "{name}"\nversion = "{version}"\ndependencies = [\n{listed}]\n'


def _written(workspace: Path, name: str) -> str:
    return (workspace / "packages" / name / "pyproject.toml").read_text()


def _apply(writes: list[Any]) -> None:
    for write in writes:
        _ = write.path.write_text(write.text)


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name, requirements in (
        ("xtr-a", []),
        ("xtr-ab", ['"xtr-a>=1.0,<2",', '"other>=3",']),
        (
            "xtr-b",
            ["\"xtr-ab[extra]>=1.0,<2; python_version >= '3.11'\",", "'xtr-a>=1.0,<2',"],
        ),
    ):
        directory = tmp_path / "packages" / name
        directory.mkdir(parents=True)
        _ = (directory / "pyproject.toml").write_text(_manifest(name, "1.3.0", requirements))
    _ = (tmp_path / "pyproject.toml").write_text('[project]\nname = "xtr"\nversion = "1.3.0"\n')
    _ = (tmp_path / "README.md").write_text(
        'version = "1.3.0"\n`uv run scripts/release.py bump 1.3.0`\n"xtr-a>=1.0,<2"\n'
    )
    monkeypatch.setattr(release, "ROOT", tmp_path)
    monkeypatch.setattr(release, "README", tmp_path / "README.md")
    return tmp_path


@pytest.fixture
def package_doc(workspace: Path) -> Path:
    doc = workspace / "packages" / "xtr-a" / "README.md"
    _ = doc.write_text('# xtr-a\n\n```toml\ndi = ["xtr-ab>=1.0,<2"]\n```\n\nacme 1.2.0\n')
    return doc


@pytest.fixture
def skill_page(workspace: Path) -> Path:
    skill = workspace / "packages" / "xtr-a" / "src" / "xtr_a" / ".agents" / "skills" / "xtr-a"
    (skill / "references").mkdir(parents=True)
    _ = (skill / "SKILL.md").write_text('di = ["xtr-ab>=1.0,<2"]\n')
    _ = (skill / "references" / "bundle.md").write_text('"xtr-a[di]>=1.0,<2"\n')
    return skill


def test_ranges_on_siblings_move_to_the_new_major_and_nothing_else_moves(workspace: Path) -> None:
    _apply(release.ranged_manifests(release.packages(), 2))

    text = _written(workspace, "xtr-b")
    assert "\"xtr-ab[extra]>=2.0,<3; python_version >= '3.11'\"" in text
    assert '"other>=3"' in _written(workspace, "xtr-ab")


def test_a_requirement_in_a_literal_string_is_ranged_too(workspace: Path) -> None:
    _apply(release.ranged_manifests(release.packages(), 2))

    assert "'xtr-a>=2.0,<3'" in _written(workspace, "xtr-b")


@pytest.mark.usefixtures("workspace")
def test_a_manifest_already_on_the_major_is_left_alone() -> None:
    planned = release.ranged_manifests(release.packages(), 1)

    assert planned == []


def test_an_unclosed_extra_is_reported_before_anything_is_written(workspace: Path) -> None:
    manifest = workspace / "packages" / "xtr-b" / "pyproject.toml"
    _ = manifest.write_text(_manifest("xtr-b", "1.3.0", ['"xtr-a[broken>=1.0,<2",']))
    before = _written(workspace, "xtr-ab")

    with pytest.raises(SystemExit, match="unclosed extras"):
        _ = release.ranged_manifests(release.packages(), 2)

    assert _written(workspace, "xtr-ab") == before


def test_the_readme_template_follows_the_version_and_its_major() -> None:
    text = 'version = "1.3.0"\n"xtr-a>=1.0,<2"\ngit tag 1.3.0\n'

    assert release.synced_readme(text, "2.0.0") == (
        'version = "2.0.0"\n"xtr-a>=2.0,<3"\ngit tag 2.0.0\n'
    )


def test_an_extra_in_a_quoted_range_keeps_its_extras() -> None:
    assert release.synced_ranges('"xtr-orm[di,console]>=1.0,<2"', 4) == (
        '"xtr-orm[di,console]>=4.0,<5"'
    )


@pytest.mark.usefixtures("workspace")
def test_a_package_readme_range_follows_the_major(package_doc: Path) -> None:
    _apply(release.synced_docs("2.0.0"))

    assert '"xtr-ab>=2.0,<3"' in package_doc.read_text()


@pytest.mark.usefixtures("workspace")
def test_a_version_a_package_readme_only_shows_is_left_alone(package_doc: Path) -> None:
    _apply(release.synced_docs("2.0.0"))

    assert "acme 1.2.0" in package_doc.read_text()


@pytest.mark.usefixtures("workspace")
def test_a_shipped_skill_and_its_references_follow_the_major(skill_page: Path) -> None:
    _apply(release.synced_docs("2.0.0"))

    assert '"xtr-ab>=2.0,<3"' in (skill_page / "SKILL.md").read_text()
    assert '"xtr-a[di]>=2.0,<3"' in (skill_page / "references" / "bundle.md").read_text()


@pytest.mark.usefixtures("workspace")
def test_a_doc_already_on_the_version_is_left_alone(package_doc: Path) -> None:
    _apply(release.synced_docs("1.3.0"))

    assert release.synced_docs("1.3.0") == []
    assert '"xtr-ab>=1.0,<2"' in package_doc.read_text()


@pytest.mark.usefixtures("workspace")
def test_check_passes_when_everything_is_on_one_version(
    capsys: pytest.CaptureFixture[str],
) -> None:
    release.check("1.3.0")

    assert capsys.readouterr().out.strip() == "1.3.0"


def test_check_names_a_package_left_behind(workspace: Path) -> None:
    manifest = workspace / "packages" / "xtr-a" / "pyproject.toml"
    _ = manifest.write_text(_manifest("xtr-a", "1.2.0", []))

    with pytest.raises(SystemExit, match=r"xtr-a 1\.2\.0"):
        release.check(None)


@pytest.mark.usefixtures("workspace")
def test_check_refuses_a_tag_the_packages_are_not_at() -> None:
    with pytest.raises(SystemExit, match=r"cannot release 1\.4\.0"):
        release.check("1.4.0")


def test_check_refuses_a_readme_on_another_version(workspace: Path) -> None:
    _ = (workspace / "README.md").write_text('version = "1.2.0"\n')

    with pytest.raises(SystemExit, match=r"not on 1\.3\.0: README\.md"):
        release.check(None)


@pytest.mark.usefixtures("workspace")
def test_check_names_a_package_doc_left_behind(package_doc: Path) -> None:
    _ = package_doc.write_text('di = ["xtr-ab>=0.0,<1"]\n')

    with pytest.raises(SystemExit, match=r"packages/xtr-a/README\.md"):
        release.check(None)


def test_check_names_an_example_left_behind(workspace: Path) -> None:
    example = workspace / "examples" / "shop"
    example.mkdir(parents=True)
    _ = (example / "pyproject.toml").write_text(_manifest("shop", "1.1.0", []))

    with pytest.raises(SystemExit, match=r"examples/shop 1\.1\.0"):
        release.check(None)


def test_check_names_a_range_left_on_another_major(workspace: Path) -> None:
    manifest = workspace / "packages" / "xtr-ab" / "pyproject.toml"
    _ = manifest.write_text(_manifest("xtr-ab", "1.3.0", ['"xtr-a>=0.0,<1",']))

    with pytest.raises(SystemExit, match=r"xtr-ab requires xtr-a>=0\.0,<1"):
        release.check(None)


def test_bump_refuses_a_version_that_is_not_x_y_z(workspace: Path) -> None:
    before = _written(workspace, "xtr-ab")

    with pytest.raises(SystemExit, match=r"not a X\.Y\.Z version"):
        release.bump("2.0")

    assert _written(workspace, "xtr-ab") == before


def test_bump_names_what_to_restore_when_it_cannot_finish(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unreachable = OSError("uv is not on the PATH")

    def refuse(found: list[Any], version: str) -> None:
        del found, version
        raise unreachable

    monkeypatch.setattr(release, "move_versions", refuse)

    with pytest.raises(SystemExit, match=r"to undo: git restore -- .*uv\.lock"):
        release.bump("2.0.0")

    assert '"xtr-a>=2.0,<3"' in _written(workspace, "xtr-ab")


@pytest.mark.usefixtures("workspace")
def test_the_recovery_pathspec_covers_every_manifest_and_lockfile() -> None:
    found = release.packages()

    pathspec = release.recovery(found, release.synced_docs("2.0.0")).split()

    assert "README.md" in pathspec
    assert "pyproject.toml" in pathspec
    assert "uv.lock" in pathspec
    assert "packages/xtr-a/pyproject.toml" in pathspec


def test_every_line_the_readme_sync_rewrites_is_still_in_the_readme() -> None:
    text = (_SCRIPT.parents[1] / "README.md").read_text()
    prefixes = release.README_VERSION.pattern.split("(", 1)[1].split(")", 1)[0].split("|")

    missing = [prefix for prefix in prefixes if not re.search(rf"{prefix}\d+\.\d+\.\d+", text)]

    assert missing == []
    assert release.DOC_RANGE.search(text) is not None

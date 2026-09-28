"""The release script keeps every package, the workspace and the README on one version."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "release.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("release", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["release"] = module
    spec.loader.exec_module(module)
    return module


release = _load()


def _manifest(name: str, version: str, requirements: list[str]) -> str:
    listed = "".join(f'    "{requirement}",\n' for requirement in requirements)
    return f'[project]\nname = "{name}"\nversion = "{version}"\ndependencies = [\n{listed}]\n'


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name, requirements in (
        ("xtr-a", []),
        ("xtr-ab", ["xtr-a>=1.0,<2", "other>=3"]),
        ("xtr-b", ["xtr-ab[extra]>=1.0,<2; python_version >= '3.11'", "xtr-a>=1.0,<2"]),
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


def test_ranges_on_siblings_move_to_the_new_major_and_nothing_else_moves(workspace: Path) -> None:
    release.rewrite_ranges(2)

    text = (workspace / "packages" / "xtr-b" / "pyproject.toml").read_text()
    assert "\"xtr-ab[extra]>=2.0,<3; python_version >= '3.11'\"" in text
    assert '"xtr-a>=2.0,<3"' in text
    other = (workspace / "packages" / "xtr-ab" / "pyproject.toml").read_text()
    assert '"other>=3"' in other


def test_an_unclosed_extra_is_reported_rather_than_crashing(workspace: Path) -> None:
    manifest = workspace / "packages" / "xtr-b" / "pyproject.toml"
    _ = manifest.write_text(_manifest("xtr-b", "1.3.0", ["xtr-a[broken>=1.0,<2"]))

    with pytest.raises(SystemExit, match="unclosed extras"):
        release.rewrite_ranges(2)


def test_the_readme_template_follows_the_version_and_its_major() -> None:
    text = 'version = "1.3.0"\n"xtr-a>=1.0,<2"\ngit tag 1.3.0\n'

    assert release.synced_readme(text, "2.0.0") == (
        'version = "2.0.0"\n"xtr-a>=2.0,<3"\ngit tag 2.0.0\n'
    )


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

    with pytest.raises(SystemExit, match=r"README\.md is not on 1\.3\.0"):
        release.check(None)


def test_check_names_an_example_left_behind(workspace: Path) -> None:
    example = workspace / "examples" / "shop"
    example.mkdir(parents=True)
    _ = (example / "pyproject.toml").write_text(_manifest("shop", "1.1.0", []))

    with pytest.raises(SystemExit, match=r"examples/shop 1\.1\.0"):
        release.check(None)

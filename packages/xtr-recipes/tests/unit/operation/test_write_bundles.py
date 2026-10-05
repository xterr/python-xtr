from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_recipes.operation.write_bundles import WriteBundles

if TYPE_CHECKING:
    from pathlib import Path

_RENDERED = '"""The root bundles."""\n\nBUNDLES = {}\n'


def test_it_renders_the_file_unindented(tmp_path: Path) -> None:
    operation = WriteBundles(tmp_path / "bundles.py", "src/app/bundles.py", _RENDERED)

    assert operation.render() == ("write src/app/bundles.py",)


def test_it_writes_the_rendered_list(tmp_path: Path) -> None:
    path = tmp_path / "src" / "app" / "bundles.py"

    WriteBundles(path, "src/app/bundles.py", _RENDERED).apply()

    assert path.read_text(encoding="utf-8") == _RENDERED


def test_it_changes_the_project() -> None:
    assert WriteBundles.changes is True

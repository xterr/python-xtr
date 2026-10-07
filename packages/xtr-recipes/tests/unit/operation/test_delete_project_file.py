from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_recipes.operation.delete_project_file import DeleteProjectFile

if TYPE_CHECKING:
    from pathlib import Path


def test_it_renders_the_display_path_unindented(tmp_path: Path) -> None:
    operation = DeleteProjectFile(tmp_path / "xtr.lock", "xtr.lock")

    assert operation.render() == ("delete xtr.lock",)


def test_it_deletes_the_file(tmp_path: Path) -> None:
    path = tmp_path / "xtr.lock"
    _ = path.write_text("{}\n", encoding="utf-8")

    DeleteProjectFile(path, "xtr.lock").apply()

    assert not path.exists()


def test_a_file_already_gone_is_nothing_to_undo(tmp_path: Path) -> None:
    DeleteProjectFile(tmp_path / "xtr.lock", "xtr.lock").apply()

    assert not (tmp_path / "xtr.lock").exists()


def test_it_changes_the_project() -> None:
    assert DeleteProjectFile.changes is True

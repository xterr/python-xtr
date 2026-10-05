from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_recipes.operation.delete_file import DeleteFile

if TYPE_CHECKING:
    from pathlib import Path


def test_it_renders_the_display_path_indented(tmp_path: Path) -> None:
    operation = DeleteFile(tmp_path / "messenger.py", "src/app/config/messenger.py")

    assert operation.render() == ("  delete src/app/config/messenger.py",)


def test_it_deletes_the_file(tmp_path: Path) -> None:
    path = tmp_path / "messenger.py"
    _ = path.write_text("BODY\n", encoding="utf-8")

    DeleteFile(path, "messenger.py").apply()

    assert not path.exists()


def test_a_file_already_gone_is_nothing_to_undo(tmp_path: Path) -> None:
    DeleteFile(tmp_path / "absent.py", "absent.py").apply()

    assert not (tmp_path / "absent.py").exists()


def test_it_changes_the_project() -> None:
    assert DeleteFile.changes is True

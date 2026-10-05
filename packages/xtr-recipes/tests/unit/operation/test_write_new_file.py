from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_recipes.operation.write_new_file import WriteNewFile

if TYPE_CHECKING:
    from pathlib import Path


def test_it_renders_the_display_path_with_the_new_suffix(tmp_path: Path) -> None:
    operation = WriteNewFile(tmp_path / "messenger.py", "src/app/config/messenger.py", "")

    assert operation.render() == ("  write src/app/config/messenger.py.new",)


def test_it_writes_beside_the_file(tmp_path: Path) -> None:
    path = tmp_path / "messenger.py"
    _ = path.write_text("MINE\n", encoding="utf-8")

    WriteNewFile(path, "messenger.py", "THEIRS\n").apply()

    assert (tmp_path / "messenger.py.new").read_text(encoding="utf-8") == "THEIRS\n"


def test_it_leaves_the_file_itself_alone(tmp_path: Path) -> None:
    path = tmp_path / "messenger.py"
    _ = path.write_text("MINE\n", encoding="utf-8")

    WriteNewFile(path, "messenger.py", "THEIRS\n").apply()

    assert path.read_text(encoding="utf-8") == "MINE\n"


def test_it_creates_the_directories_above_the_file(tmp_path: Path) -> None:
    path = tmp_path / "src" / "app" / "messenger.py"

    WriteNewFile(path, "src/app/messenger.py", "BODY\n").apply()

    assert (tmp_path / "src" / "app" / "messenger.py.new").is_file()


def test_it_changes_the_project() -> None:
    assert WriteNewFile.changes is True

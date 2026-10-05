from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_recipes.operation.write_file import WriteFile

if TYPE_CHECKING:
    from pathlib import Path


def test_it_renders_the_display_path_indented(tmp_path: Path) -> None:
    display = "src/app/config/messenger.py"

    assert WriteFile(tmp_path / display, display, "").render() == (f"  write {display}",)


def test_it_writes_the_content(tmp_path: Path) -> None:
    path = tmp_path / "config.py"

    WriteFile(path, "config.py", "BODY\n").apply()

    assert path.read_text(encoding="utf-8") == "BODY\n"


def test_it_creates_the_directories_above_the_file(tmp_path: Path) -> None:
    path = tmp_path / "src" / "app" / "config" / "messenger.py"

    WriteFile(path, "src/app/config/messenger.py", "BODY\n").apply()

    assert path.is_file()


def test_it_replaces_what_the_file_held(tmp_path: Path) -> None:
    path = tmp_path / "config.py"
    _ = path.write_text("OLD\n", encoding="utf-8")

    WriteFile(path, "config.py", "NEW\n").apply()

    assert path.read_text(encoding="utf-8") == "NEW\n"


def test_it_changes_the_project() -> None:
    assert WriteFile.changes is True

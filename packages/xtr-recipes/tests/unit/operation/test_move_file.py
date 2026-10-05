from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_recipes.operation.move_file import MoveFile

if TYPE_CHECKING:
    from pathlib import Path


def _move(directory: Path) -> MoveFile:
    return MoveFile(
        directory / "messenger.py",
        "config/messenger.py",
        directory / "messenger.py.removed",
        "config/messenger.py.removed",
        "edited",
    )


def test_it_renders_both_paths_and_the_reason(tmp_path: Path) -> None:
    assert _move(tmp_path).render() == (
        "  moved config/messenger.py to config/messenger.py.removed (edited)",
    )


def test_it_moves_the_file_keeping_its_content(tmp_path: Path) -> None:
    _ = (tmp_path / "messenger.py").write_text("EDITED\n", encoding="utf-8")

    _move(tmp_path).apply()

    assert not (tmp_path / "messenger.py").exists()
    assert (tmp_path / "messenger.py.removed").read_text(encoding="utf-8") == "EDITED\n"


def test_it_changes_the_project() -> None:
    assert MoveFile.changes is True

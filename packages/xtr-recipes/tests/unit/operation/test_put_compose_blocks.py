from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_recipes.operation.put_compose_blocks import PutComposeBlocks

if TYPE_CHECKING:
    from pathlib import Path

_PACKAGE = "xtr-orm"
_SECTIONS = {"services": ("  database:",)}
_WRITTEN = "services:\n###> xtr-orm ###\n  database:\n###< xtr-orm ###\n"


def test_it_renders_the_file_being_written_or_cleared(tmp_path: Path) -> None:
    path = tmp_path / "compose.yaml"

    assert PutComposeBlocks(path, "compose.yaml", _PACKAGE, _SECTIONS).render() == (
        "  write compose.yaml",
    )
    assert PutComposeBlocks(path, "compose.yaml", _PACKAGE, {}).render() == (
        "  clear compose.yaml",
    )


def test_it_writes_the_blocks_into_a_file_that_does_not_exist(tmp_path: Path) -> None:
    path = tmp_path / "compose.yaml"

    PutComposeBlocks(path, "compose.yaml", _PACKAGE, _SECTIONS).apply()

    assert path.read_text(encoding="utf-8") == _WRITTEN


def test_clearing_the_last_blocks_deletes_the_file(tmp_path: Path) -> None:
    path = tmp_path / "compose.yaml"
    _ = path.write_text(_WRITTEN, encoding="utf-8")

    PutComposeBlocks(path, "compose.yaml", _PACKAGE, {}).apply()

    assert not path.exists()


def test_clearing_keeps_what_the_owner_wrote(tmp_path: Path) -> None:
    path = tmp_path / "compose.yaml"
    _ = path.write_text(f"{_WRITTEN}  app:\n    image: app\n", encoding="utf-8")

    PutComposeBlocks(path, "compose.yaml", _PACKAGE, {}).apply()

    assert path.read_text(encoding="utf-8") == "services:\n  app:\n    image: app\n"


def test_it_changes_the_project() -> None:
    assert PutComposeBlocks.changes is True

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_recipes.operation.put_block import PutBlock

if TYPE_CHECKING:
    from pathlib import Path

_PACKAGE = "xtr-messenger"
_BLOCK = """\
# >>> xtr-messenger
# MESSENGER_DSN=
# <<< xtr-messenger
"""


def test_it_renders_the_file_being_written(tmp_path: Path) -> None:
    operation = PutBlock(tmp_path / ".env", ".env", _PACKAGE, ("# MESSENGER_DSN=",))

    assert operation.render() == ("  write .env",)


def test_it_writes_the_block_into_a_file_that_does_not_exist(tmp_path: Path) -> None:
    path = tmp_path / ".env"

    PutBlock(path, ".env", _PACKAGE, ("# MESSENGER_DSN=",)).apply()

    assert path.read_text(encoding="utf-8") == _BLOCK


def test_it_keeps_what_the_file_already_held(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    _ = path.write_text("OTHER=1\n", encoding="utf-8")

    PutBlock(path, ".env", _PACKAGE, ("# MESSENGER_DSN=",)).apply()

    assert path.read_text(encoding="utf-8") == f"OTHER=1\n\n{_BLOCK}"


def test_applying_it_twice_leaves_the_file_the_same(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    operation = PutBlock(path, ".env", _PACKAGE, ("# MESSENGER_DSN=",))

    operation.apply()
    operation.apply()

    assert path.read_text(encoding="utf-8") == _BLOCK


def test_it_changes_the_project() -> None:
    assert PutBlock.changes is True

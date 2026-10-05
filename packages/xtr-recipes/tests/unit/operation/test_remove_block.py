from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_recipes.operation.remove_block import RemoveBlock

if TYPE_CHECKING:
    from pathlib import Path

_PACKAGE = "xtr-messenger"
_FILE = """\
OTHER=1

# >>> xtr-messenger
MESSENGER_DSN=amqp://localhost
# <<< xtr-messenger
"""


def test_it_renders_the_file_being_cleared(tmp_path: Path) -> None:
    assert RemoveBlock(tmp_path / ".env", ".env", _PACKAGE).render() == ("  clear .env",)


def test_it_removes_the_block(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    _ = path.write_text(_FILE, encoding="utf-8")

    RemoveBlock(path, ".env", _PACKAGE).apply()

    assert path.read_text(encoding="utf-8") == "OTHER=1\n"


def test_it_leaves_a_file_without_the_block_as_it_is(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    _ = path.write_text("OTHER=1\n", encoding="utf-8")

    RemoveBlock(path, _PACKAGE, _PACKAGE).apply()

    assert path.read_text(encoding="utf-8") == "OTHER=1\n"


def test_it_changes_the_project() -> None:
    assert RemoveBlock.changes is True

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_recipes.operation.write_lock import WriteLock
from xtr_recipes.recipe_lock import LockEntry, RecipeLock

if TYPE_CHECKING:
    from pathlib import Path

_LOCK = RecipeLock({"xtr-messenger": LockEntry(recipe="abc")})


def test_it_renders_the_lock_unindented(tmp_path: Path) -> None:
    assert WriteLock(_LOCK, tmp_path).render() == ("write xtr.lock",)


def test_it_writes_the_lock_into_the_project(tmp_path: Path) -> None:
    WriteLock(_LOCK, tmp_path).apply()

    assert (tmp_path / "xtr.lock").read_text(encoding="utf-8") == _LOCK.dumps()


def test_it_changes_the_project() -> None:
    assert WriteLock.changes is True

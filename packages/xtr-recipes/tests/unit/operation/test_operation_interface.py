from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_recipes.operation.bundle_note import BundleNote
from xtr_recipes.operation.delete_file import DeleteFile
from xtr_recipes.operation.keep_file import KeepFile
from xtr_recipes.operation.notes import Notes
from xtr_recipes.operation.operation_interface import OperationInterface
from xtr_recipes.operation.put_block import PutBlock
from xtr_recipes.operation.remove_block import RemoveBlock
from xtr_recipes.operation.section import Section
from xtr_recipes.operation.write_bundles import WriteBundles
from xtr_recipes.operation.write_file import WriteFile
from xtr_recipes.operation.write_lock import WriteLock
from xtr_recipes.operation.write_new_file import WriteNewFile
from xtr_recipes.recipe_lock import RecipeLock

if TYPE_CHECKING:
    from pathlib import Path


def _every_operation(tmp_path: Path) -> tuple[OperationInterface, ...]:
    path = tmp_path / "config.py"
    return (
        Section("configure", "xtr-messenger"),
        WriteFile(path, "config.py", ""),
        WriteNewFile(path, "config.py", ""),
        DeleteFile(path, "config.py"),
        KeepFile("config.py", "edited"),
        PutBlock(tmp_path / ".env", ".env", "xtr-messenger", ("KEY=1",)),
        RemoveBlock(tmp_path / ".env", ".env", "xtr-messenger"),
        BundleNote("MessengerBundle", "listed"),
        Notes(run=("app go",)),
        WriteBundles(tmp_path / "bundles.py", "bundles.py", ""),
        WriteLock(RecipeLock(), tmp_path),
    )


def test_every_operation_satisfies_the_interface(tmp_path: Path) -> None:
    for operation in _every_operation(tmp_path):
        assert isinstance(operation, OperationInterface)


def test_a_class_without_the_methods_does_not_satisfy_it() -> None:
    assert not isinstance(object(), OperationInterface)


def test_a_reporting_operation_is_told_from_one_that_writes(tmp_path: Path) -> None:
    writing = [
        type(operation).__name__ for operation in _every_operation(tmp_path) if operation.changes
    ]

    assert writing == [
        "WriteFile",
        "WriteNewFile",
        "DeleteFile",
        "PutBlock",
        "RemoveBlock",
        "WriteBundles",
        "WriteLock",
    ]

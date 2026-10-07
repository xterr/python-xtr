"""The steps a sync is made of, and the plan that holds them.

Every step answers twice — :meth:`~.operation_interface.OperationInterface.render`
for the person reading and
:meth:`~.operation_interface.OperationInterface.apply` for the project on disk
— so printing a sync without doing it is not a second implementation but the
same plan read differently. A step that only reports says ``changes = False``,
which is how a plan with nothing to do is told from one with work in it.
"""

from __future__ import annotations

from .bundle_note import BundleNote
from .delete_file import DeleteFile
from .delete_project_file import DeleteProjectFile
from .keep_file import KeepFile
from .move_file import MoveFile
from .notes import Notes
from .operation_interface import OperationInterface
from .plan import Plan
from .put_block import PutBlock
from .remove_block import RemoveBlock
from .section import Section
from .write_bundles import WriteBundles
from .write_file import WriteFile
from .write_lock import WriteLock
from .write_new_file import WriteNewFile

__all__ = [
    "BundleNote",
    "DeleteFile",
    "DeleteProjectFile",
    "KeepFile",
    "MoveFile",
    "Notes",
    "OperationInterface",
    "Plan",
    "PutBlock",
    "RemoveBlock",
    "Section",
    "WriteBundles",
    "WriteFile",
    "WriteLock",
    "WriteNewFile",
]

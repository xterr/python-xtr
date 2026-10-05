"""The five commands that drive a project's recipes.

Importing this package declares all of them: ``@as_command`` writes to the
console's registry as each module is read, which is why the entry point
imports this and nothing else. A command holds no logic of its own — it reads
``--project-dir``, asks :mod:`~xtr_recipes.command_support` for a
synchronizer, reports the plan and returns an exit code. That module sits
beside this package rather than in it, so a command can reach it without this
package being imported back into the command that it imports.
"""

from __future__ import annotations

from .add_command import AddCommand
from .install_command import InstallCommand
from .remove_command import RemoveCommand
from .show_command import ShowCommand
from .sync_command import SyncCommand

__all__ = [
    "AddCommand",
    "InstallCommand",
    "RemoveCommand",
    "ShowCommand",
    "SyncCommand",
]

"""The two commands that create a project.

Importing this package declares both: ``@as_command`` writes to the console's
registry as each module is read, which is why the entry point imports this and
nothing else. Neither holds logic of its own; both hand their options to
:func:`xtr_cli.command_support.scaffold`.
"""

from __future__ import annotations

from .init_command import InitCommand
from .new_command import NewCommand

__all__ = ["InitCommand", "NewCommand"]

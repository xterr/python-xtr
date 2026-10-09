"""The commands: two that create a project, and one that serves it.

Importing this package declares all of them: ``@as_command`` writes to the
console's registry as each module is read, which is why the entry point imports
this and nothing else.
"""

from __future__ import annotations

from .init_command import InitCommand
from .new_command import NewCommand
from .serve_command import ServeCommand

__all__ = ["InitCommand", "NewCommand", "ServeCommand"]

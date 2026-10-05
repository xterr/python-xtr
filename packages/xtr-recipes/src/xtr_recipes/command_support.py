"""What the commands share: the project, the synchronizer, and running ``uv``.

Every command in :mod:`xtr_recipes.command` reaches the library through this
module rather than building a
:class:`~xtr_recipes.synchronizer.Synchronizer` or starting a process itself.
That keeps one answer to "which project, read how" for all five, and leaves a
test a single place to put a synchronizer reading recipes it wrote and a
recorder in place of the process that would be started.

It sits beside that package rather than in it so that the package's
``__init__`` can import every command module — which is what declares the
commands — without a command module importing the package back.
"""

from __future__ import annotations

import re
import subprocess
from typing import TYPE_CHECKING

from xtr_console import ExitCode, escape

from .project import Project
from .synchronizer import Synchronizer

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from xtr_console import ConsoleStyle

    from .exception import RecipesError
    from .operation.plan import Plan

__all__ = [
    "build_synchronizer",
    "change_dependency",
    "failed",
    "load_project",
    "normalise",
    "report",
    "run",
    "write",
]

_NOTHING = "nothing to do"
_SYNC = ("uv", "run", "xtr-recipes", "recipes:sync", "--project-dir")
# PEP 503 normalisation, so a package named on a command line matches the
# dependency list however it was spelled.
_SEPARATORS = re.compile(r"[-_.]+")


def load_project(project_dir: Path | None) -> Project:
    """Return the project at ``project_dir``, or the one around the current directory."""
    if project_dir is None:
        return Project.discover()
    return Project.load(project_dir)


def build_synchronizer(project: Project) -> Synchronizer:
    """Return the synchronizer a command works ``project`` through.

    The one seam between a command and the installed recipes: a test replaces
    this with a synchronizer reading manifests it wrote itself, so no package
    has to be installed for a command to be exercised.
    """
    return Synchronizer(project)


def run(argv: Sequence[str], cwd: Path) -> int:
    """Run ``argv`` in ``cwd`` and return its exit code.

    The non-zero code is the answer, not an exception: a failing ``uv`` has
    already said why on its own streams, and the command's own job is to stop
    rather than to explain it again.
    """
    completed = subprocess.run(argv, cwd=cwd, check=False)  # noqa: S603 — argv is built here.
    return completed.returncode


def change_dependency(io: ConsoleStyle, project: Project, argv: Sequence[str]) -> int:
    """Change the project's dependencies with ``argv``, then sync it afresh.

    The sync cannot be this process: ``argv`` changes the environment under
    the running interpreter, which has already read the recipes of the
    installation as it was when it started. A new process reads the new one.

    Args:
        io: Where the failure is reported.
        project: The application whose dependencies change.
        argv: The dependency command to run, ``uv`` and all.

    Returns:
        The sync's exit code, or :attr:`~xtr_console.ExitCode.FAILURE` when
        the dependency change itself failed and no sync was attempted.
    """
    if run(argv, project.project_dir) != 0:
        io.error(escape(f"{' '.join(argv)} failed"))
        return ExitCode.FAILURE
    return run((*_SYNC, str(project.project_dir)), project.project_dir)


def report(io: ConsoleStyle, plan: Plan) -> None:
    """Print every step of ``plan``, or say there is nothing in it."""
    lines = plan.render()
    if not lines:
        io.text(_NOTHING)
        return
    write(io, lines)


def write(io: ConsoleStyle, lines: Sequence[str]) -> None:
    """Print lines a recipe composed, with nothing in them read as markup.

    A recipe's own text reaches these lines — a note, an ignore pattern, the
    extra named by ``install <package>[di]`` — and a bracketed word is markup
    to the console, which would print that one as ``install xtr-security``.
    """
    for line in lines:
        io.text(escape(line))


def failed(io: ConsoleStyle, error: RecipesError) -> int:
    """Report what a recipe cannot get past, and fail the run.

    Every one of these errors carries a message naming the package and the key
    or file at fault, so there is nothing a traceback would add for whoever
    has to fix the manifest or the project. The message quotes what it found,
    so it is escaped for the same reason :func:`write` escapes a plan.
    """
    io.error(escape(str(error)))
    return ExitCode.FAILURE


def normalise(package: str) -> str:
    """Return a distribution name as a dependency list spells it."""
    return _SEPARATORS.sub("-", package.strip()).lower()

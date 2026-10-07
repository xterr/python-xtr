"""``recipes:remove``: drop a dependency, then undo what it had configured."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003 — the console reads annotations at runtime.
from typing import final

from xtr_console import ConsoleStyle, as_command

from xtr_recipes import command_support
from xtr_recipes.exception import RecipesError

__all__ = ["RemoveCommand"]

# ``--`` ends uv's own options, so a package name that begins with a dash is
# passed through as a package, not parsed as a flag of ``uv remove``.
_UV_REMOVE = ("uv", "remove", "--")


@as_command("recipes:remove")
@final
class RemoveCommand:
    """Drop a dependency from the project, then unconfigure what it left.

    The lock alone says what to take back, so the recipe does not have to be
    installed any more by the time the sync runs — which it will not be. That
    sync is a fresh process, because removing has changed the environment
    under this one.
    """

    async def __call__(
        self,
        io: ConsoleStyle,
        package: str,
        *,
        project_dir: Path | None = None,
    ) -> int:
        """Remove a package from the project, then unconfigure what it left.

        Args:
            io: Where a failure is reported.
            package: The distribution to remove.
            project_dir: The project to remove it from; the nearest one at or
                above the current directory by default.

        Returns:
            The sync's exit code, or a failure when the removal itself failed.
        """
        try:
            project = command_support.load_project(project_dir)
        except RecipesError as error:
            return command_support.failed(io, error)
        return command_support.change_dependency(io, project, (*_UV_REMOVE, package))

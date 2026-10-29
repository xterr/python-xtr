"""``recipes:remove``: drop a dependency, then undo what it had configured."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003 — the console reads annotations at runtime.
from typing import final

from xtr_console import ConsoleStyle, as_command

from xtr_recipes import command_support
from xtr_recipes.exception import RecipesError

__all__ = ["RemoveCommand"]

_UV_REMOVE = ("uv", "remove")
# A package depended on for development only is in the ``dev`` group, which a
# plain ``uv remove`` does not look in.
_DEV = "--dev"
# ``--`` ends uv's own options, so a package name that begins with a dash is
# passed through as a package, not parsed as a flag of ``uv remove``.
_END_OF_OPTIONS = "--"


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
            package: The distribution to remove; one the project depends on for
                development only is taken out of the dev dependency group.
            project_dir: The project to remove it from; the nearest one at or
                above the current directory by default.

        Returns:
            The sync's exit code, or a failure when the removal itself failed.
        """
        try:
            project = command_support.load_project(project_dir)
        except RecipesError as error:
            return command_support.failed(io, error)
        dev_only = command_support.normalise(package) in project.dev_dependencies
        group = (_DEV,) if dev_only else ()
        argv = (*_UV_REMOVE, *group, _END_OF_OPTIONS, package)
        return command_support.change_dependency(io, project, argv)

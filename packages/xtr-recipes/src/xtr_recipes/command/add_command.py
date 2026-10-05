"""``recipes:add``: add a dependency, then configure what it ships."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003 — the console reads annotations at runtime.
from typing import final

from xtr_console import ConsoleStyle, as_command

from xtr_recipes import command_support
from xtr_recipes.exception import RecipesError

__all__ = ["AddCommand"]

_UV_ADD = ("uv", "add")


@as_command("recipes:add")
@final
class AddCommand:
    """Add a requirement to the project, then sync the recipes it brought.

    One step for what is otherwise two: the dependency is installed, and
    whatever recipe arrived with it is applied. The sync runs as a fresh
    process, because installing has changed the environment under this one.
    """

    async def __call__(
        self,
        io: ConsoleStyle,
        requirement: str,
        *,
        project_dir: Path | None = None,
    ) -> int:
        """Add a requirement to the project, then configure what it brought.

        Args:
            io: Where a failure is reported.
            requirement: The requirement to add, extras and version and all,
                exactly as a dependency list spells it.
            project_dir: The project to add it to; the nearest one at or above
                the current directory by default.

        Returns:
            The sync's exit code, or a failure when the install itself failed.
        """
        try:
            project = command_support.load_project(project_dir)
        except RecipesError as error:
            return command_support.failed(io, error)
        return command_support.change_dependency(io, project, (*_UV_ADD, requirement))

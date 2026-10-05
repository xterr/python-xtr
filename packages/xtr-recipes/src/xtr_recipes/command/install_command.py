"""``recipes:install``: apply one package's recipe again, whatever the lock says."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003 — the console reads annotations at runtime.
from typing import final

from xtr_console import ConsoleStyle, ExitCode, as_command

from xtr_recipes import command_support
from xtr_recipes.exception import RecipesError
from xtr_recipes.sync_options import SyncOptions

__all__ = ["InstallCommand"]


@as_command("recipes:install")
@final
class InstallCommand:
    """Re-apply one package's recipe and leave the rest of the lock alone.

    Unconditional, which is what makes it the way to restore a file that went
    missing: a sync would find the recipe unchanged and do nothing, while this
    renders it again. The rest of the project is read but never planned, so
    one package cannot be repaired at another's expense.
    """

    async def __call__(
        self,
        io: ConsoleStyle,
        package: str,
        *,
        force: bool = False,
        project_dir: Path | None = None,
    ) -> int:
        """Apply one package's recipe to the project.

        Args:
            io: Where the steps are reported.
            package: The distribution whose recipe to apply.
            force: Overwrite a file that was edited or adopted, instead of
                putting the new content beside it.
            project_dir: The project to apply it to; the nearest one at or
                above the current directory by default.
        """
        try:
            synchronizer = command_support.build_synchronizer(
                command_support.load_project(project_dir)
            )
            plan = synchronizer.plan(SyncOptions(only=package, force=force))
            command_support.report(io, plan)
            synchronizer.apply(plan)
        except RecipesError as error:
            return command_support.failed(io, error)
        return ExitCode.SUCCESS

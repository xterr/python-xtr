"""``recipes:sync``: bring the project in line with the recipes it depends on."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003 — the console reads annotations at runtime.
from typing import TYPE_CHECKING, final

from xtr_console import ConsoleStyle, ExitCode, as_command

from xtr_recipes import command_support
from xtr_recipes.exception import RecipesError

if TYPE_CHECKING:
    from xtr_recipes.operation.plan import Plan

__all__ = ["SyncCommand"]

_IN_SYNC = "recipes are in sync"


@as_command("recipes:sync")
@final
class SyncCommand:
    """Configure what is new, re-apply what changed, undo what is gone.

    The whole run is planned before any of it is done, so the three ways of
    asking are one code path: ``--check`` refuses a project the plan would
    change, ``--dry-run`` prints the plan and stops, and the default prints it
    and carries it out. Nothing cares how a package arrived or left, so the
    second run of any of them finds nothing to do.
    """

    async def __call__(
        self,
        io: ConsoleStyle,
        *,
        check: bool = False,
        dry_run: bool = False,
        project_dir: Path | None = None,
    ) -> int:
        """Apply every recipe the project's direct dependencies ship.

        Args:
            io: Where the plan is reported.
            check: Fail when a sync would change the project, and write
                nothing; what a continuous integration job asks.
            dry_run: Print what would be done, and write nothing.
            project_dir: The project to sync; the nearest one at or above the
                current directory by default.
        """
        try:
            synchronizer = command_support.build_synchronizer(
                command_support.load_project(project_dir)
            )
            plan = synchronizer.plan()
            if check:
                return _checked(io, plan)
            command_support.report(io, plan)
            if not dry_run:
                synchronizer.apply(plan)
        except RecipesError as error:
            return command_support.failed(io, error)
        return ExitCode.SUCCESS


def _checked(io: ConsoleStyle, plan: Plan) -> int:
    """Report a project a sync would change, and fail; else say it is in sync.

    A plan can hold steps and still change nothing — a heading, a file left
    alone, a package skipped — so what is asked here is whether anything would
    be written, not whether there is anything to say.
    """
    if not plan.has_changes:
        io.text(_IN_SYNC)
        return ExitCode.SUCCESS
    command_support.write(io, plan.render())
    return ExitCode.FAILURE

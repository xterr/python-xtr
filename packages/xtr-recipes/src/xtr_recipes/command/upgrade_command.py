"""``recipes:upgrade``: move every xtr package to its newest release, then sync."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003 — the console reads annotations at runtime.
from typing import Final, final

from xtr_console import ConsoleStyle, ExitCode, as_command

from xtr_recipes import command_support
from xtr_recipes.exception import RecipesError

__all__ = ["UpgradeCommand"]

_UV_LOCK = ("uv", "lock")
_UPGRADE_PACKAGE = "--upgrade-package"
_FAMILY_PREFIX: Final = "xtr-"
_NOTHING_TO_UPGRADE = "no xtr package is installed"


@as_command("recipes:upgrade")
@final
class UpgradeCommand:
    """Upgrade every installed xtr package together, then sync the recipes.

    The packages are released together, at one version, and only packages at
    one version were tested together. Upgrading one of them leaves its
    siblings where the lock has them, so each is named to the lock: every xtr
    package the environment holds — a direct dependency or not — moves to its
    newest release, and nothing else does. The sync runs as a fresh process,
    whose ``uv run`` installs what the lock now names, and re-applies any
    recipe the new releases changed.
    """

    async def __call__(self, io: ConsoleStyle, *, project_dir: Path | None = None) -> int:
        """Upgrade every installed xtr package, then configure what changed.

        Args:
            io: Where a failure is reported.
            project_dir: The project to upgrade; the nearest one at or above
                the current directory by default.

        Returns:
            The sync's exit code, or a failure when the lock itself failed.
        """
        try:
            project = command_support.load_project(project_dir)
        except RecipesError as error:
            return command_support.failed(io, error)
        family = [
            name
            for name in command_support.installed_distributions()
            if name.startswith(_FAMILY_PREFIX)
        ]
        if not family:
            io.text(_NOTHING_TO_UPGRADE)
            return ExitCode.SUCCESS
        upgrades = [argument for name in family for argument in (_UPGRADE_PACKAGE, name)]
        return command_support.change_dependency(io, project, (*_UV_LOCK, *upgrades))

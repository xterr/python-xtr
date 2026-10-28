"""``project:new``: create an application in a new directory."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003 — the console reads annotations at runtime.
from typing import final

from xtr_console import ConsoleStyle, as_command

from xtr_cli import command_support

__all__ = ["NewCommand"]


@as_command("project:new", aliases="new")
@final
class NewCommand:
    """Create a new application in a new directory.

    Nothing is asked: a console application by default, a web application with
    ``--webapp``. The packages are installed with ``uv``, and each one's recipe
    is applied, before the command ends.
    """

    async def __call__(  # noqa: PLR0913 — one parameter per option.
        self,
        io: ConsoleStyle,
        directory: Path,
        *,
        webapp: bool = False,
        name: str | None = None,
        python: str | None = None,
        no_git: bool = False,
        dry_run: bool = False,
        local_packages: Path | None = None,
    ) -> int:
        """Create a new application in a new directory.

        Args:
            io: Where the steps are reported.
            directory: Where to create it; it must be missing or empty.
            webapp: Make a web application, with a database, a message bus and security.
            name: The project's name; the directory's name by default.
            python: The 3.<minor> version to pin; the one running this tool by default.
            no_git: Do not initialise a git repository.
            dry_run: Print the files and commands, and write nothing.
            local_packages: Install the xtr packages from this directory of
                sources, editable, instead of the package index.

        Returns:
            The exit code.
        """
        return command_support.scaffold(
            io,
            command="new",
            directory=directory,
            webapp=webapp,
            name=name,
            python=python,
            git=not no_git,
            dry_run=dry_run,
            local_packages=local_packages,
        )

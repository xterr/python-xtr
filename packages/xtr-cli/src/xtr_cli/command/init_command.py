"""``project:init``: create an application in the current directory."""

from __future__ import annotations

from pathlib import Path
from typing import final

from xtr_console import ConsoleStyle, as_command

from xtr_cli import command_support

__all__ = ["InitCommand"]


@as_command("project:init", aliases="init")
@final
class InitCommand:
    """Create a new application in the current directory.

    Nothing is asked: a console application by default, a web application with
    ``--webapp``. The directory must hold nothing but version-control or editor
    metadata; an existing git repository is kept rather than initialised again.
    """

    async def __call__(  # noqa: PLR0913 — one parameter per option.
        self,
        io: ConsoleStyle,
        *,
        webapp: bool = False,
        name: str | None = None,
        python: str | None = None,
        no_git: bool = False,
        dry_run: bool = False,
        local_packages: Path | None = None,
    ) -> int:
        """Create a new application in the current directory.

        Args:
            io: Where the steps are reported.
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
            command="init",
            directory=Path.cwd(),
            webapp=webapp,
            name=name,
            python=python,
            git=not no_git,
            dry_run=dry_run,
            local_packages=local_packages,
        )

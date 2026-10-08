"""``project:init``: create an application in the current directory."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, final

from xtr_console import ConsoleStyle, Option, as_command

from xtr_cli import command_support

__all__ = ["InitCommand"]


@as_command("project:init", aliases="init")
@final
class InitCommand:
    """Create a new application, from a template, in the current directory.

    The directory must hold nothing but version-control or editor metadata;
    an existing git repository is kept rather than initialised again.
    """

    async def __call__(  # noqa: PLR0913 — one parameter per option.
        self,
        io: ConsoleStyle,
        *,
        template: str | None = None,
        name: str | None = None,
        add_ons: Annotated[
            str | None,
            Option(
                name="--with",
                help="More packages to start with, comma-separated: orm:sqlite+postgres,messenger.",
            ),
        ] = None,
        python: str | None = None,
        no_git: bool = False,
        dry_run: bool = False,
        local_packages: Path | None = None,
    ) -> int:
        """Create a new application, from a template, in the current directory.

        Args:
            io: Where the questions are asked and the steps reported.
            template: cli or webapp, or a directory holding a template.toml.
            name: The project's name; the directory's name by default.
            add_ons: The ``--with`` add-ons.
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
            template=template,
            name=name,
            add_ons=add_ons,
            python=python,
            git=not no_git,
            dry_run=dry_run,
            local_packages=local_packages,
        )

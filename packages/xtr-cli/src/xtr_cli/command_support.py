"""What the commands share: the questions, the scaffolder, and how a run is reported.

``project:new`` and ``project:init`` differ only in where the project goes, so
both hand their options to :func:`scaffold`. It sits beside the
:mod:`xtr_cli.command` package rather than in it, so a command module can
import it without the package being imported back.
"""

from __future__ import annotations

import re
import sys
from typing import TYPE_CHECKING

from xtr_console import ExitCode, escape

from . import __version__
from .add_on_catalog import AddOnCatalog
from .exception import CliError, UnsupportedPythonError
from .project_name import ProjectName
from .project_questions import ProjectQuestions
from .project_settings import ProjectSettings
from .scaffolder import Scaffolder
from .subprocess_runner import SubprocessRunner
from .template_catalog import TemplateCatalog

if TYPE_CHECKING:
    from pathlib import Path

    from xtr_console import ConsoleStyle

    from .process_runner_interface import ProcessRunnerInterface
    from .scaffold_plan import ScaffoldPlan

__all__ = ["build_runner", "build_scaffolder", "default_python", "scaffold"]

_PYTHON = re.compile(r"^3\.(?P<minor>\d+)$")
_OLDEST_MINOR = 11


def build_runner() -> ProcessRunnerInterface:
    """Return what the commands start ``uv``, ``git`` and a server through.

    The one seam between a command and a real process: a test replaces this
    with a recorder.
    """
    return SubprocessRunner()


def build_scaffolder() -> Scaffolder:
    """Return the scaffolder a command makes its project with.

    The one seam between a command and the processes it starts: a test
    replaces this with a scaffolder over a recorder, so a project is planned
    and written without installing anything.
    """
    return Scaffolder(build_runner(), __version__)


def default_python() -> str:
    """Return the ``3.<minor>`` of the interpreter this tool runs on."""
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def scaffold(  # noqa: PLR0913 — one keyword per option the two commands share.
    io: ConsoleStyle,
    *,
    command: str,
    directory: Path | None,
    template: str | None,
    name: str | None,
    add_ons: str | None,
    python: str | None,
    git: bool,
    dry_run: bool,
    local_packages: Path | None,
) -> int:
    """Settle the project from the options and the answers, then plan it and make it.

    Returns:
        Success once the project is made, or printed for a dry run;
        :attr:`~xtr_console.ExitCode.INVALID` when no directory was given;
        :attr:`~xtr_console.ExitCode.FAILURE` when a setting is refused or a
        step fails.
    """
    questions = ProjectQuestions(io, TemplateCatalog.default(), AddOnCatalog.default())
    try:
        target = questions.directory(directory)
        if target is None:
            io.error("Give the directory to create the project in: xtr new <directory>")
            return ExitCode.INVALID
        settings = _settings(
            questions,
            command=command,
            directory=target.expanduser().resolve(),
            template=template,
            name=name,
            add_ons=add_ons,
            python=python if python is not None else default_python(),
            git=git,
            local_packages=local_packages,
        )
        scaffolder = build_scaffolder()
        plan = scaffolder.plan(settings)
    except CliError as error:
        io.error(escape(str(error)))
        return ExitCode.FAILURE
    _summarise(io, settings)
    if dry_run:
        for line in plan.render():
            io.text(escape(line))
        return ExitCode.SUCCESS
    if not questions.confirm():
        io.warning("Nothing was written.")
        return ExitCode.SUCCESS
    try:
        scaffolder.apply(plan, lambda line: io.text(escape(line)))
    except CliError as error:
        io.error(escape(str(error)))
        return ExitCode.FAILURE
    _finish(io, settings, plan)
    return ExitCode.SUCCESS


def _settings(  # noqa: PLR0913 — the settings, one keyword each.
    questions: ProjectQuestions,
    *,
    command: str,
    directory: Path,
    template: str | None,
    name: str | None,
    add_ons: str | None,
    python: str,
    git: bool,
    local_packages: Path | None,
) -> ProjectSettings:
    """Settle every setting, asking for what is missing, refusing what cannot be used."""
    Scaffolder.check_directory(directory)
    project_name = ProjectName.parse(name if name is not None else directory.name)
    version = _PYTHON.match(python)
    if version is None or int(version.group("minor")) < _OLDEST_MINOR:
        raise UnsupportedPythonError(python)
    source = questions.template(template)
    chosen = TemplateCatalog.default().load(source)
    return ProjectSettings(
        command=command,
        directory=directory,
        name=project_name,
        template=chosen,
        template_source=source,
        add_ons=questions.add_ons(add_ons, chosen.name),
        python=python,
        name_given=name is not None,
        git=git,
        local_packages=local_packages.expanduser().resolve() if local_packages else None,
    )


def _summarise(io: ConsoleStyle, settings: ProjectSettings) -> None:
    """Print what is about to be made, and the command that makes it with no question."""
    add_ons = ", ".join(
        f"{choice.add_on.name} ({', '.join(choice.variants)})"
        if choice.variants
        else choice.add_on.name
        for choice in settings.add_ons
    )
    io.section(escape(f"{settings.name.distribution} — the {settings.template.name} template"))
    io.listing(
        escape(line)
        for line in (
            f"directory: {settings.directory}",
            f"add-ons:   {add_ons or 'none'}",
            f"python:    {settings.python}",
        )
    )
    io.text("The same, with no question asked:")
    io.text(escape(f"  {settings.command_line()}"))
    io.newline()


def _finish(io: ConsoleStyle, settings: ProjectSettings, plan: ScaffoldPlan) -> None:
    """Say the project is ready, and what to run first."""
    io.success(escape(f"{settings.name.distribution} is ready in {settings.directory}"))
    steps = plan.next_steps
    if settings.command == "new":
        steps = (f"cd {settings.directory}", *steps)
    if steps:
        io.section("Next steps")
        io.listing(escape(step) for step in steps)

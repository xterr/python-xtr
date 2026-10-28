"""Scaffolder: plans a new project from its settings, then makes it."""

from __future__ import annotations

import json
import re
import shlex
from typing import TYPE_CHECKING, final

from .exception import DirectoryNotEmptyError, StepFailedError
from .scaffold_plan import ScaffoldPlan

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from pathlib import Path

    from .process_runner_interface import ProcessRunnerInterface
    from .project_settings import ProjectSettings

__all__ = ["Scaffolder"]

_PYPROJECT = "pyproject.toml"
_RECIPES = "xtr-recipes"
# Metadata a directory may already hold and still count as empty.
_IGNORED = frozenset({".git", ".hg", ".idea", ".vscode", ".DS_Store"})
# A release version: what the xtr requirements are pinned to the major of.
_RELEASE = re.compile(r"^(?P<major>\d+)\.\d+\.\d+$")
# A requirement already carrying a version, a URL or a marker is left as written.
_SPECIFIED = re.compile(r"[<>=!~@;]")
_NAME_END = re.compile(r"[\s\[<>=!~@;]")


@final
class Scaffolder:
    """Turns settings into a plan, and a plan into a project.

    Making a project is writing the template's files, then handing over to
    ``uv``: ``uv add`` installs the requirements and locks them, and the
    project's own ``xtr-recipes recipes:sync`` applies each installed
    package's recipe — the bundle list, the ``.env`` and ignore blocks — with
    the versions the project actually installed.

    Every xtr package moves with one shared version, so an unversioned xtr
    requirement is pinned to this tool's major version: a template is always
    installed with the packages it was written for.
    """

    __slots__ = ("_runner", "_version")

    def __init__(self, runner: ProcessRunnerInterface, version: str) -> None:
        """Run commands through ``runner``; pin the xtr requirements to ``version``'s major."""
        self._runner = runner
        self._version = version

    @staticmethod
    def check_directory(directory: Path) -> None:
        """Refuse a directory that is a file, or holds anything but metadata.

        Raises:
            DirectoryNotEmptyError: When ``directory`` is in the way.
        """
        if not directory.exists():
            return
        if not directory.is_dir():
            raise DirectoryNotEmptyError(directory, (directory.name,))
        found = tuple(sorted(entry.name for entry in directory.iterdir()))
        in_the_way = tuple(name for name in found if name not in _IGNORED)
        if in_the_way:
            raise DirectoryNotEmptyError(directory, in_the_way)

    def plan(self, settings: ProjectSettings) -> ScaffoldPlan:
        """Work the project out in full, writing nothing.

        Raises:
            InvalidTemplateError: When the template cannot be rendered.
        """
        values = settings.values()
        template = settings.template
        files = template.render(values)
        if settings.local_packages is not None:
            sources = _sources(settings.local_packages)
            files = tuple(
                (path, text + sources if path == _PYPROJECT else text) for path, text in files
            )
        dependencies = self._pinned(template.dependencies)
        dev_dependencies = self._pinned(template.dev_dependencies)
        commands: list[tuple[str, ...]] = []
        if dependencies:
            commands.append(("uv", "add", "--", *dependencies))
        if dev_dependencies:
            commands.append(("uv", "add", "--dev", "--", *dev_dependencies))
        if _RECIPES in {_name(each) for each in (*dependencies, *dev_dependencies)}:
            commands.append(("uv", "run", _RECIPES, "recipes:sync"))
        if settings.git and not (settings.directory / ".git").exists():
            commands.append(("git", "init", "--quiet"))
        return ScaffoldPlan(
            directory=settings.directory,
            files=files,
            commands=tuple(commands),
            next_steps=template.steps(values),
        )

    def apply(self, plan: ScaffoldPlan, report: Callable[[str], None]) -> None:
        """Make the project ``plan`` describes, reporting each step as it starts.

        Raises:
            DirectoryNotEmptyError: When the directory filled up since it was
                checked.
            StepFailedError: When a command fails; the commands after it are
                not run, and what was made so far is left in place.
        """
        self.check_directory(plan.directory)
        for path, text in plan.files:
            report(f"write {path}")
            target = plan.directory.joinpath(*path.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            _ = target.write_text(text, encoding="utf-8")
        for argv in plan.commands:
            report(f"run   {shlex.join(argv)}")
            code = self._runner.run(argv, plan.directory)
            if code != 0:
                raise StepFailedError(argv, plan.directory, code)

    def _pinned(self, requirements: Iterable[str]) -> tuple[str, ...]:
        """Pin each unversioned xtr requirement to this tool's major version."""
        release = _RELEASE.match(self._version)
        if release is None:
            return tuple(requirements)
        major = int(release.group("major"))
        return tuple(
            f"{requirement}>={major}.0,<{major + 1}"
            if _name(requirement).startswith("xtr-") and not _SPECIFIED.search(requirement)
            else requirement
            for requirement in requirements
        )


def _name(requirement: str) -> str:
    """Return the distribution a requirement names, without extras or version."""
    stripped = requirement.strip()
    end = _NAME_END.search(stripped)
    return (stripped[: end.start()] if end is not None else stripped).lower()


def _sources(local_packages: Path) -> str:
    """Return a ``[tool.uv.sources]`` table installing every package found there, editable.

    Every package is listed, not only the ones the project names: a source in
    the project's own manifest applies to the packages it pulls in as well,
    so a sibling that is not yet published still resolves.
    """
    root = local_packages.expanduser().resolve()
    lines: list[str] = []
    for manifest in sorted(root.glob(f"xtr-*/{_PYPROJECT}")):
        path = json.dumps(manifest.parent.as_posix())
        lines.append(f"{manifest.parent.name} = {{ path = {path}, editable = true }}")
    return "\n[tool.uv.sources]\n" + "".join(f"{line}\n" for line in lines)

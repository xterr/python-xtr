from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_console import Application, ApplicationTester

from xtr_recipes import command_support
from xtr_recipes.bundle_requirements import BundleRequirements
from xtr_recipes.command import (
    AddCommand,
    InstallCommand,
    RemoveCommand,
    ShowCommand,
    SyncCommand,
)
from xtr_recipes.synchronizer import Synchronizer

from .fake_recipe_source import FakeRecipeSource, recipe_content
from .project_builder import build_project

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    import pytest
    from xtr_dependency_injection.bundle.bundle import AnyBundle

    from xtr_recipes.project import Project

__all__ = [
    "CONFIG",
    "DECLARED",
    "MESSENGER",
    "MESSENGER_MANIFEST",
    "RENDERED",
    "TARGET",
    "TEMPLATE",
    "ProcessRecorder",
    "build_tester",
    "install_recipes",
    "messenger_project",
    "record_processes",
    "snapshot",
]

DECLARED = (AddCommand, InstallCommand, RemoveCommand, ShowCommand, SyncCommand)
"""The command classes, named here so importing this module declares all five.

``@as_command`` writes to the console's registry as each module is read, so a
tester only finds a command whose module something has imported.
"""


@final
class ProcessRecorder:
    """Answers with a prepared exit code and remembers what it was asked to run."""

    def __init__(self, codes: Sequence[int]) -> None:
        self.calls: list[tuple[tuple[str, ...], Path]] = []
        self._codes: tuple[int, ...] = tuple(codes)

    def __call__(self, argv: Sequence[str], cwd: Path) -> int:
        """Record one call and answer with the code prepared for it."""
        self.calls.append((tuple(argv), cwd))
        return self._codes[len(self.calls) - 1]


MESSENGER = "xtr-messenger"
TEMPLATE = "files/config/messenger.py.tmpl"
TARGET = "xtr_messenger.bundle:MessengerBundle"
CONFIG = "src/app/config/messenger.py"
RENDERED = "MESSENGER = app\n"

_BODY = "MESSENGER = ${app}\n"

MESSENGER_MANIFEST = f"""\
[files]
"config/messenger.py" = "{TEMPLATE}"

[env]
MESSENGER_DSN = ""

[gitignore]
lines = ["/var/messenger"]

[notes]
check = ["<script> debug:bundles"]
"""
"""A recipe with one file, one environment key, one ignore line and a note.

No bundle, so no bundle class has to be loadable for it to count as installed.
"""


def build_tester() -> ApplicationTester:
    """A tester over the declared commands, with exceptions left to propagate."""
    return ApplicationTester(Application("xtr-recipes", catch_exceptions=False))


def messenger_project(directory: Path) -> Project:
    """Write the smallest application depending on the messenger recipe."""
    return build_project(directory, dependencies=[MESSENGER])


def install_recipes(
    monkeypatch: pytest.MonkeyPatch,
    manifests: Mapping[str, str],
    known: Mapping[str, type[AnyBundle]] | None = None,
) -> None:
    """Make every command read ``manifests`` instead of the installed recipes.

    Replaces the one seam a command reaches the library through, so the
    commands under test run against recipes written in the test rather than
    against whatever happens to be installed in the process.

    Args:
        monkeypatch: Undoes the replacement when the test ends.
        manifests: Each distribution mapped to its manifest text.
        known: The bundle classes the installation carries; a target absent
            from it cannot be loaded, which is what makes a package skipped.
    """
    source = FakeRecipeSource(
        {name: recipe_content(manifest, {TEMPLATE: _BODY}) for name, manifest in manifests.items()}
    )
    loadable: Mapping[str, type[AnyBundle]] = known if known is not None else {}

    def load(target: str) -> type[AnyBundle] | None:
        return loadable.get(target)

    requirements = BundleRequirements(load)

    def build(project: Project) -> Synchronizer:
        return Synchronizer(project, source, requirements)

    monkeypatch.setattr(command_support, "build_synchronizer", build)


def record_processes(monkeypatch: pytest.MonkeyPatch, *codes: int) -> ProcessRecorder:
    """Stand a recorder in for the processes a command would start.

    Args:
        monkeypatch: Undoes the replacement when the test ends.
        codes: The exit code each successive call answers with, in order.

    Returns:
        The recorder, to read the calls back off.
    """
    recorder = ProcessRecorder(codes)
    monkeypatch.setattr(command_support, "run", recorder)
    return recorder


def snapshot(directory: Path) -> dict[str, str]:
    """Every file under ``directory`` mapped to its text, for a no-write assertion."""
    return {
        str(path.relative_to(directory)): path.read_text(encoding="utf-8")
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }

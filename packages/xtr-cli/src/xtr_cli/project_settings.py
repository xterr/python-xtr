"""ProjectSettings: everything decided about a new project before anything is written."""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from .add_on_choice import AddOnChoice
    from .project_name import ProjectName
    from .template import Template

__all__ = ["ProjectSettings"]


@final
@dataclass(frozen=True, slots=True)
class ProjectSettings:
    """The answers a project is made from — from the command line, the questions, or both.

    Attributes:
        command: The command that makes it, ``new`` or ``init``, for :meth:`command_line`.
        directory: Where the project is made, absolute.
        name: The project's name.
        template: The template it is made from.
        template_source: The template as it was asked for: a shipped name or a directory.
        add_ons: The add-ons it starts with.
        python: The ``3.<minor>`` version it is pinned to.
        name_given: Whether the name was asked for rather than read off the directory.
        git: Whether a git repository is initialised in it.
        local_packages: A directory of xtr package sources to install from, editable,
            instead of the package index.
    """

    command: str
    directory: Path
    name: ProjectName
    template: Template
    template_source: str
    add_ons: tuple[AddOnChoice, ...]
    python: str
    name_given: bool = False
    git: bool = True
    local_packages: Path | None = None

    def values(self) -> dict[str, str]:
        """Return what the template's placeholders are filled with.

        ``minor`` is the part of the Python version after ``3.``, so a tool
        naming versions as ``py313`` can be given ``py3${minor}``.
        """
        return {
            "name": self.name.distribution,
            "app": self.name.app,
            "python": self.python,
            "minor": self.python.partition(".")[2],
        }

    def command_line(self) -> str:
        """Return the command making this same project with no question asked.

        Printed before anything is written, so an answered run can be repeated
        in a script or a CI job, or pasted into documentation.
        """
        parts = ["uvx", "xtr-cli", self.command]
        if self.command == "new":
            parts.append(_shown(self.directory))
        parts.append(f"--template={self.template_source}")
        if self.name_given:
            parts.append(f"--name={self.name.distribution}")
        if self.add_ons:
            parts.append(f"--with={','.join(choice.spelling for choice in self.add_ons)}")
        parts.append(f"--python={self.python}")
        if not self.git:
            parts.append("--no-git")
        if self.local_packages is not None:
            parts.append(f"--local-packages={self.local_packages}")
        parts.append("-n")
        return shlex.join(parts)


def _shown(directory: Path) -> str:
    """Return ``directory`` relative to the working directory when it lies under it."""
    try:
        return str(directory.relative_to(Path.cwd()))
    except ValueError:
        return str(directory)

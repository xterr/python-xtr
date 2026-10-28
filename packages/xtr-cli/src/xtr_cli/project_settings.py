"""ProjectSettings: everything decided about a new project before anything is written."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from pathlib import Path

    from .project_name import ProjectName
    from .template import Template

__all__ = ["ProjectSettings"]


@final
@dataclass(frozen=True, slots=True)
class ProjectSettings:
    """Everything a project is made from, settled from the command line.

    Attributes:
        command: The command that makes it, ``new`` or ``init``.
        directory: Where the project is made, absolute.
        name: The project's name.
        template: The template it is made from.
        python: The ``3.<minor>`` version it is pinned to.
        git: Whether a git repository is initialised in it.
        local_packages: A directory of xtr package sources to install from, editable,
            instead of the package index.
    """

    command: str
    directory: Path
    name: ProjectName
    template: Template
    python: str
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

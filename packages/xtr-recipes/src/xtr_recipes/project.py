"""Project: where an application lives, what it depends on, and how it is run."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import final

from .application_package import ApplicationPackage
from .exception import ProjectNotFoundError, UnreadableFileError
from .normalise import normalise

__all__ = ["Project"]

_PYPROJECT = "pyproject.toml"
# A requirement's name ends at the first extra, marker, URL, space or operator.
_NAME_END = re.compile(r"[\s;<>=!~@(\[]")


@final
@dataclass(frozen=True, slots=True)
class Project:
    """An application on disk, read once from its ``pyproject.toml``.

    Built by :meth:`load` or :meth:`discover`; both read the manifest and
    find the application package, so a value of this type is known to point
    at an application that exists.

    The application package is the one package holding ``kernel.py`` (see
    :class:`~xtr_recipes.application_package.ApplicationPackage`); nothing in
    ``pyproject.toml`` names it.

    Attributes:
        project_dir: The directory that holds ``pyproject.toml``.
        app: The application's dotted import name — ``bookshop`` for
            ``src/bookshop/``, ``acme.shop`` for ``src/acme/shop/``.
        package_dir: The directory of the application package, the one
            holding ``kernel.py``; a recipe writes its files below it.
        dependencies: The PEP 503-normalised names of the direct dependencies
            (``[project].dependencies``), with extras, markers and versions
            removed.
        dev_dependencies: The development dependencies, read the same way from
            the ``dev`` dependency group (``[dependency-groups].dev``) and from
            the list uv kept before dependency groups existed,
            ``[tool.uv].dev-dependencies``; uv installs the two as one group.
            A name already in :attr:`dependencies` is left out: the application
            runs with that package, so it is a runtime dependency. An
            ``{include-group = ...}`` entry is not followed — these are the
            names ``uv add --dev`` writes and ``uv remove --dev`` takes out,
            and an included group is a table of its own.
        script: The first ``[project.scripts]`` name, or ``None`` when none is
            declared.
    """

    project_dir: Path
    app: str
    package_dir: Path
    dependencies: tuple[str, ...]
    dev_dependencies: tuple[str, ...]
    script: str | None

    @classmethod
    def discover(cls, start: Path | None = None) -> Project:
        """Load the project in the nearest ancestor of ``start`` holding a manifest.

        Args:
            start: Where to begin the upward search; the current working
                directory when ``None``.

        Returns:
            The project found.

        Raises:
            ProjectNotFoundError: When no ``pyproject.toml`` lies at or above
                ``start``, or the application package cannot be found.
        """
        origin = start if start is not None else Path.cwd()
        for directory in (origin, *origin.parents):
            if (directory / _PYPROJECT).is_file():
                return cls.load(directory)
        raise ProjectNotFoundError(origin, "no pyproject.toml here or in any parent directory")

    @classmethod
    def load(cls, project_dir: Path) -> Project:
        """Load the project rooted at ``project_dir``.

        Args:
            project_dir: The directory holding ``pyproject.toml``.

        Returns:
            The project.

        Raises:
            ProjectNotFoundError: When ``project_dir`` holds no
                ``pyproject.toml``, or when not exactly one package holds a
                ``kernel.py``.
        """
        manifest = project_dir / _PYPROJECT
        if not manifest.is_file():
            raise ProjectNotFoundError(project_dir, f"no {_PYPROJECT} here")
        data = _read(manifest)
        package = ApplicationPackage.find(project_dir)
        dependencies = _dependencies(data)
        return cls(
            project_dir=project_dir,
            app=package.name,
            package_dir=package.directory,
            dependencies=dependencies,
            dev_dependencies=_dev_dependencies(data, dependencies),
            script=_script(data),
        )


def _read(path: Path) -> dict[str, object]:
    """Read a ``pyproject.toml`` into a mapping of untyped values."""
    try:
        with path.open("rb") as handle:
            data: dict[str, object] = tomllib.load(handle)
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        raise UnreadableFileError(path, f"not valid TOML: {error}") from error
    return data


def _dependencies(data: dict[str, object]) -> tuple[str, ...]:
    """Return the direct dependency names, normalised, each kept once in order."""
    project = data.get("project")
    return _names(project.get("dependencies") if isinstance(project, dict) else None)


def _dev_dependencies(data: dict[str, object], runtime: tuple[str, ...]) -> tuple[str, ...]:
    """Return the development dependency names not in ``runtime``, each kept once in order."""
    groups = data.get("dependency-groups")
    tool = data.get("tool")
    settings = tool.get("uv") if isinstance(tool, dict) else None
    names = (
        *_names(groups.get("dev") if isinstance(groups, dict) else None),
        *_names(settings.get("dev-dependencies") if isinstance(settings, dict) else None),
    )
    return tuple(name for name in dict.fromkeys(names) if name not in runtime)


def _names(raw: object) -> tuple[str, ...]:
    """Return the names a list of requirement strings holds, normalised, each kept once in order.

    Whatever else the list holds is skipped — a dependency group's
    ``{include-group = ...}`` table among them — and so is a value that is not
    a list.
    """
    if not isinstance(raw, list):
        return ()
    names: list[str] = []
    for entry in raw:
        if not isinstance(entry, str):
            continue
        name = _requirement_name(entry)
        if name:
            names.append(name)
    return tuple(dict.fromkeys(names))


def _requirement_name(requirement: str) -> str:
    """Return the PEP 503-normalised name of a requirement string."""
    stripped = requirement.strip()
    match = _NAME_END.search(stripped)
    name = stripped[: match.start()] if match is not None else stripped
    return normalise(name)


def _script(data: dict[str, object]) -> str | None:
    """Return the first ``[project.scripts]`` name, or ``None``."""
    project = data.get("project")
    if not isinstance(project, dict):
        return None
    scripts = project.get("scripts")
    if not isinstance(scripts, dict):
        return None
    for name in scripts:
        return str(name)
    return None

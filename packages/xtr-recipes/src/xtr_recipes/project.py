"""Project: where an application lives, what it depends on, and how it is run."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import final

from .exception import ProjectNotFoundError

__all__ = ["Project"]

_PYPROJECT = "pyproject.toml"
_APP_SETTING = "[tool.xtr-recipes] app"
_NAME_SETTING = "[project].name"
# PEP 503 normalisation: a run of dashes, underscores or dots is one separator.
_SEPARATORS = re.compile(r"[-_.]+")
# A requirement's name ends at the first extra, marker, URL, space or operator.
_NAME_END = re.compile(r"[\s;<>=!~@(\[]")


@final
@dataclass(frozen=True, slots=True)
class Project:
    """An application on disk, read once from its ``pyproject.toml``.

    Built by :meth:`load` or :meth:`discover`; both read the manifest and
    resolve the application package, so a value of this type is known to point
    at an application that exists.

    Attributes:
        project_dir: The directory that holds ``pyproject.toml``.
        app: The application import name — the package found under ``src/`` or
            at the project root.
        dependencies: The PEP 503-normalised names of the direct dependencies
            (``[project].dependencies``), with extras, markers and versions
            removed; dependency groups are not included.
        script: The first ``[project.scripts]`` name, or ``None`` when none is
            declared.
    """

    project_dir: Path
    app: str
    dependencies: tuple[str, ...]
    script: str | None

    @property
    def package_dir(self) -> Path:
        """The directory of the application package, where a recipe writes files.

        ``src/<app>/`` when that is where the package is, otherwise ``<app>/``
        at the project root. Both :meth:`load` and :meth:`discover` have
        already checked that one of them exists, so the second is also the
        answer for a project whose package has since been deleted.
        """
        found = _package_dir(self.project_dir, self.app)
        return found if found is not None else self.project_dir / self.app

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
                ``start``, or the application package cannot be resolved.
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
                ``pyproject.toml``, or the application package resolves to
                neither ``src/<app>/`` nor ``<app>/``, naming the setting the
                application name came from.
        """
        manifest = project_dir / _PYPROJECT
        if not manifest.is_file():
            raise ProjectNotFoundError(project_dir, f"no {_PYPROJECT} here")
        data = _read(manifest)
        app, setting = _app_name(data)
        if _package_dir(project_dir, app) is None:
            raise ProjectNotFoundError(
                project_dir,
                f"{app!r} resolves to neither src/{app}/ nor {app}/",
                setting,
            )
        return cls(
            project_dir=project_dir,
            app=app,
            dependencies=_dependencies(data),
            script=_script(data),
        )


def _read(path: Path) -> dict[str, object]:
    """Read a ``pyproject.toml`` into a mapping of untyped values."""
    with path.open("rb") as handle:
        data: dict[str, object] = tomllib.load(handle)
    return data


def _app_name(data: dict[str, object]) -> tuple[str, str]:
    """Return the application import name and the setting it came from.

    ``[tool.xtr-recipes] app`` wins when set to a string; otherwise
    ``[project].name`` normalised to an identifier. The name may be empty when
    neither is set, which ``_package_dir`` then rejects.
    """
    tool = data.get("tool")
    if isinstance(tool, dict):
        recipes = tool.get("xtr-recipes")
        if isinstance(recipes, dict):
            app = recipes.get("app")
            if isinstance(app, str):
                return app, _APP_SETTING
    project = data.get("project")
    if isinstance(project, dict):
        name = project.get("name")
        if isinstance(name, str):
            return _SEPARATORS.sub("_", name).lower(), _NAME_SETTING
    return "", _NAME_SETTING


def _package_dir(project_dir: Path, app: str) -> Path | None:
    """Return the directory of the application package, or ``None`` if absent."""
    if not app:
        return None
    for candidate in (project_dir / "src" / app, project_dir / app):
        if candidate.is_dir():
            return candidate
    return None


def _dependencies(data: dict[str, object]) -> tuple[str, ...]:
    """Return the direct dependency names, normalised, each kept once in order."""
    project = data.get("project")
    if not isinstance(project, dict):
        return ()
    raw = project.get("dependencies")
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
    return _SEPARATORS.sub("-", name.strip()).lower()


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

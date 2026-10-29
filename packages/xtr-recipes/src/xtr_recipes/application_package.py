"""ApplicationPackage: the package that holds the application's ``kernel.py``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from .exception import ProjectNotFoundError

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["ApplicationPackage"]

_KERNEL = "kernel.py"
_INIT = "__init__.py"
_SRC = "src"
# Directories that never hold the application package: environments, caches,
# generated output, test suites and runtime data.
_SKIPPED = frozenset(
    ("venv", "node_modules", "tests", "build", "dist", "site", "__pycache__", "migrations", "var")
)
_NONE_FOUND = f"no {_KERNEL} was found in an application package under {_SRC}/ or the project root"
_KEEP_ONE = f"keep {_KERNEL} in the application package only"


@final
@dataclass(frozen=True, slots=True)
class ApplicationPackage:
    """The application package of a project, found by the ``kernel.py`` at its root.

    The kernel is built in ``kernel.py`` from the package it sits in, so that
    file is the one place the application names its own package. Nothing else
    — no ``pyproject.toml`` setting, no distribution name — is consulted, so
    the two can never disagree.

    Attributes:
        name: The dotted import name, ``acme.shop`` for ``src/acme/shop/``.
        directory: The package directory, the one holding ``kernel.py``.
    """

    name: str
    directory: Path

    @classmethod
    def find(cls, project_dir: Path) -> ApplicationPackage:
        """Find the one package holding a ``kernel.py`` in ``project_dir``.

        ``src/`` is searched first and the project root only when ``src/``
        holds none. Only importable packages are descended into — every
        directory on the way has an ``__init__.py`` and a name that is an
        identifier — so a namespace of packages works (``src/acme/shop/``) and
        a stray ``kernel.py`` in a plain directory does not count. Hidden
        directories (their names are not identifiers) and those that never
        hold the application (``tests``, ``build``, ``venv``, ...) are skipped.
        A package holding a
        ``kernel.py`` is not searched further: a module of that name below it
        belongs to the application.

        Args:
            project_dir: The directory holding ``pyproject.toml``.

        Returns:
            The application package.

        Raises:
            ProjectNotFoundError: When no package holds a ``kernel.py``, or
                more than one does.
        """
        src = project_dir / _SRC
        found = _search(src, ()) if src.is_dir() else []
        if not found:
            # src/ was searched already, even when it is itself a package.
            found = [
                package
                for package in _search(project_dir, ())
                if package.name.partition(".")[0] != _SRC
            ]
        if not found:
            raise ProjectNotFoundError(project_dir, _NONE_FOUND)
        if len(found) > 1:
            listed = ", ".join(
                f"{package.name} ({package.directory.relative_to(project_dir).as_posix()}/)"
                for package in found
            )
            raise ProjectNotFoundError(
                project_dir,
                f"{_KERNEL} was found in several packages, {listed}; {_KEEP_ONE}",
            )
        return found[0]


def _search(directory: Path, names: tuple[str, ...]) -> list[ApplicationPackage]:
    """Return every package below ``directory`` holding a ``kernel.py``, in name order."""
    found: list[ApplicationPackage] = []
    for child in sorted(directory.iterdir()):
        if not _is_package(child):
            continue
        dotted = (*names, child.name)
        if (child / _KERNEL).is_file():
            found.append(ApplicationPackage(".".join(dotted), child))
        else:
            found.extend(_search(child, dotted))
    return found


def _is_package(path: Path) -> bool:
    """Tell whether ``path`` is an importable package the application may be in."""
    name = path.name
    return name.isidentifier() and name not in _SKIPPED and (path / _INIT).is_file()

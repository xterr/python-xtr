"""WebEntryPointFinder: the project around a directory, and what in it serves the web."""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, final

from .exception import ProjectNotFoundError, WebEntryPointNotFoundError
from .web_entry_point import WebEntryPoint

if TYPE_CHECKING:
    from collections.abc import Iterator

__all__ = ["WebEntryPointFinder"]

_PYPROJECT = "pyproject.toml"
# A script importing one of these starts a server itself.
_SERVERS = frozenset({"uvicorn", "hypercorn", "granian"})
# A script named like this is the web entry point by convention.
_WEB_SUFFIXES = ("-web", "_web", "-server", "_server")
# The classes whose module-level instance is an ASGI application.
_ASGI_CLASSES = frozenset({"FastAPI", "Starlette", "Litestar"})
# Directories that hold no application code, at whatever depth they appear.
_SKIPPED = frozenset(
    {"__pycache__", "node_modules", "build", "dist", "tests", "test", "migrations", "var"}
)


@final
class WebEntryPointFinder:
    """Finds what serves a project, reading its files and running nothing.

    A web console script comes first: it is the application's own way of
    serving, environment loading included. A script counts when its module
    imports a server — ``uvicorn``, ``hypercorn`` or ``granian`` — or its name
    ends in ``-web`` or ``-server``. Only a project with no such script is
    searched for a module-level ASGI object instead. Every module is read with
    :mod:`ast`, never imported.
    """

    __slots__ = ()

    @staticmethod
    def project_dir(start: Path | None = None) -> Path:
        """Return the nearest directory at or above ``start`` holding a ``pyproject.toml``.

        Raises:
            ProjectNotFoundError: When there is none.
        """
        origin = (start if start is not None else Path.cwd()).expanduser().resolve()
        for directory in (origin, *origin.parents):
            if (directory / _PYPROJECT).is_file():
                return directory
        raise ProjectNotFoundError(origin)

    def find(self, project_dir: Path) -> tuple[WebEntryPoint, ...]:
        """Return every web entry point of the project, the scripts first and alone if any."""
        scripts = tuple(
            WebEntryPoint("script", name)
            for name, target in _scripts(project_dir).items()
            if name.endswith(_WEB_SUFFIXES) or _imports_a_server(project_dir, target)
        )
        if scripts:
            return scripts
        return tuple(WebEntryPoint("asgi", target) for target in _asgi_objects(project_dir))

    @staticmethod
    def resolve(project_dir: Path, given: str) -> WebEntryPoint:
        """Return the entry point ``--entrypoint`` names: a script, or ``module:attribute``.

        Raises:
            WebEntryPointNotFoundError: When ``given`` is neither one of the
                project's scripts nor a ``module:attribute``.
        """
        module, separator, attribute = given.partition(":")
        if separator:
            if all(part.isidentifier() for part in module.split(".")) and attribute.isidentifier():
                return WebEntryPoint("asgi", given)
            raise WebEntryPointNotFoundError(project_dir, f"{given!r} is not a module:attribute")
        if given in _scripts(project_dir):
            return WebEntryPoint("script", given)
        raise WebEntryPointNotFoundError(
            project_dir,
            f"no script {given!r} in [project.scripts]; give a script name or a module:attribute",
        )


def _scripts(project_dir: Path) -> dict[str, str]:
    """Return ``[project.scripts]``, each name mapped to its ``module:function``."""
    try:
        with (project_dir / _PYPROJECT).open("rb") as handle:
            data: dict[str, object] = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        # A manifest that cannot be read has no scripts to offer; the ASGI search still runs.
        return {}
    project = data.get("project")
    scripts = project.get("scripts") if isinstance(project, dict) else None
    if not isinstance(scripts, dict):
        return {}
    return {str(name): str(target) for name, target in scripts.items() if isinstance(target, str)}


def _roots(project_dir: Path) -> tuple[Path, ...]:
    """Return where the project's modules live: ``src/`` when present, and the project itself."""
    source = project_dir / "src"
    return (source, project_dir) if source.is_dir() else (project_dir,)


def _module_file(project_dir: Path, module: str) -> Path | None:
    """Return the file defining ``module``, looked for where the project keeps its code."""
    parts = module.split(".")
    for root in _roots(project_dir):
        for candidate in (
            root.joinpath(*parts).with_suffix(".py"),
            root.joinpath(*parts, "__init__.py"),
        ):
            if candidate.is_file():
                return candidate
    return None


def _parse(file: Path) -> ast.Module | None:
    """Parse ``file``, or return ``None`` for one that cannot be read as Python."""
    try:
        return ast.parse(file.read_text(encoding="utf-8"), str(file))
    except (OSError, UnicodeDecodeError, SyntaxError, ValueError):
        # Not this tool's to report: a broken module is simply not an entry point.
        return None


def _imports_a_server(project_dir: Path, target: str) -> bool:
    """Report whether the module a script runs imports a server."""
    file = _module_file(project_dir, target.partition(":")[0].strip())
    tree = _parse(file) if file is not None else None
    if tree is None:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module]
        else:
            continue
        if any(name.partition(".")[0] in _SERVERS for name in names):
            return True
    return False


def _asgi_objects(project_dir: Path) -> list[str]:
    """Return every module-level ASGI application, as ``module:attribute``, sorted."""
    found: set[str] = set()
    for root in _roots(project_dir):
        for file in _modules(root, project_dir):
            parts = list(file.relative_to(root).with_suffix("").parts)
            if parts[-1] == "__init__":
                parts = parts[:-1]
            if not parts or parts[-1] == "__main__" or not all(p.isidentifier() for p in parts):
                continue
            tree = _parse(file)
            if tree is not None:
                found.update(f"{'.'.join(parts)}:{name}" for name in _asgi_names(tree))
    return sorted(found)


def _modules(root: Path, project_dir: Path) -> Iterator[Path]:
    """Yield the Python files under ``root``, leaving out tooling, tests and other roots."""
    for path in sorted(root.iterdir()):
        if path.name.startswith(".") or path.name in _SKIPPED:
            continue
        if path.is_dir():
            if path == project_dir / "src" or (path / "pyvenv.cfg").exists():
                continue
            yield from _modules(path, project_dir)
        elif path.suffix == ".py":
            yield path


def _asgi_names(tree: ast.Module) -> Iterator[str]:
    """Yield the module-level names bound to a new ASGI application."""
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            target, value = node.target, node.value
        else:
            continue
        if not isinstance(target, ast.Name) or not isinstance(value, ast.Call):
            continue
        called = value.func
        name = called.id if isinstance(called, ast.Name) else getattr(called, "attr", None)
        if name in _ASGI_CLASSES:
            yield target.id

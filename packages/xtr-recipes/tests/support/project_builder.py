from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_recipes.project import Project

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

__all__ = ["build_project", "write_package"]


def write_package(root: Path, app: str, *, kernel: bool = True) -> Path:
    """Write the package ``app`` (dotted) below ``root``, every level with an ``__init__.py``.

    The innermost package is given a ``kernel.py``, which is what marks it as
    the application's, unless ``kernel`` is false.
    """
    package = root
    for part in app.split("."):
        package /= part
        package.mkdir(parents=True, exist_ok=True)
        _ = (package / "__init__.py").write_text(f'"""The {part} package."""\n', encoding="utf-8")
    if kernel:
        _ = (package / "kernel.py").write_text('"""The kernel."""\n', encoding="utf-8")
    return package


def build_project(
    directory: Path,
    *,
    app: str = "app",
    dependencies: Sequence[str] = (),
    dev_dependencies: Sequence[str] = (),
    script: str | None = "app",
) -> Project:
    """Write the smallest application a sync can run against, and load it.

    The application package ``app`` (dotted) is written under ``src/`` with
    its ``kernel.py``; the distribution is named after it.
    """
    name = app.replace(".", "-")
    listed = ", ".join(f'"{dependency}"' for dependency in dependencies)
    body = f'[project]\nname = "{name}"\ndependencies = [{listed}]\n'
    if script is not None:
        body += f'\n[project.scripts]\n{script} = "{app}.__main__:main"\n'
    if dev_dependencies:
        dev = ", ".join(f'"{dependency}"' for dependency in dev_dependencies)
        body += f"\n[dependency-groups]\ndev = [{dev}]\n"
    _ = (directory / "pyproject.toml").write_text(body, encoding="utf-8")
    _ = write_package(directory / "src", app)
    return Project.load(directory)

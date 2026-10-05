from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_recipes.project import Project

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

__all__ = ["build_project"]


def build_project(
    directory: Path,
    *,
    name: str = "app",
    dependencies: Sequence[str] = (),
    script: str | None = "app",
) -> Project:
    """Write the smallest application a sync can run against, and load it."""
    app = name.replace("-", "_")
    listed = ", ".join(f'"{dependency}"' for dependency in dependencies)
    body = f'[project]\nname = "{name}"\ndependencies = [{listed}]\n'
    if script is not None:
        body += f'\n[project.scripts]\n{script} = "{app}.__main__:main"\n'
    _ = (directory / "pyproject.toml").write_text(body, encoding="utf-8")
    package = directory / "src" / app
    package.mkdir(parents=True, exist_ok=True)
    _ = (package / "__init__.py").write_text(f'"""The {app} application."""\n', encoding="utf-8")
    return Project.load(directory)

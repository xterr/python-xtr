from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_console import Application, ApplicationTester

from xtr_cli import AddOnCatalog, ProjectName, ProjectSettings, TemplateCatalog
from xtr_cli.command import InitCommand, NewCommand

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["DECLARED", "build_settings", "build_tester", "write_template"]

DECLARED = (InitCommand, NewCommand)
"""Named so importing this module declares both commands."""


def build_tester() -> ApplicationTester:
    """A tester over the declared commands, with exceptions left to propagate."""
    return ApplicationTester(Application("xtr", catch_exceptions=False), width=400)


def build_settings(  # noqa: PLR0913 — every setting a test may vary.
    directory: Path,
    *,
    template: str = "cli",
    add_ons: str = "",
    command: str = "new",
    name_given: bool = False,
    git: bool = True,
    local_packages: Path | None = None,
) -> ProjectSettings:
    """Settings for a project in ``directory``, from a shipped template."""
    return ProjectSettings(
        command=command,
        directory=directory,
        name=ProjectName.parse(directory.name),
        template=TemplateCatalog.default().load(template),
        template_source=template,
        add_ons=AddOnCatalog.default().parse(add_ons, template),
        python="3.13",
        name_given=name_given,
        git=git,
        local_packages=local_packages,
    )


def write_template(directory: Path, manifest: str, files: dict[str, str] | None = None) -> Path:
    """Write a template directory holding ``manifest`` and ``files``; return it."""
    directory.mkdir(parents=True, exist_ok=True)
    _ = (directory / "template.toml").write_text(manifest, encoding="utf-8")
    for path, text in (files or {}).items():
        target = directory / path
        target.parent.mkdir(parents=True, exist_ok=True)
        _ = target.write_text(text, encoding="utf-8")
    return directory

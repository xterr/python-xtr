"""Each shipped template, made for real from the working tree's packages, runs and checks clean.

Slow and networked — ``uv`` resolves the third-party packages — so it runs only when
``XTR_CLI_SCAFFOLD=1`` is set.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.scaffold,
    pytest.mark.skipif(
        os.environ.get("XTR_CLI_SCAFFOLD") != "1", reason="set XTR_CLI_SCAFFOLD=1 to scaffold"
    ),
]

_PACKAGES = Path(__file__).resolve().parents[3]
_CHECKS = (
    ("uv", "run", "ruff", "check"),
    ("uv", "run", "ruff", "format", "--check"),
    ("uv", "run", "basedpyright"),
    ("uv", "run", "ty", "check"),
    ("uv", "run", "pytest", "-q", "-p", "no:cacheprovider"),
    ("uv", "run", "xtr-recipes", "recipes:sync", "--check"),
)


def _run(argv: tuple[str, ...], cwd: Path) -> str:
    environment = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}
    completed = subprocess.run(  # noqa: S603 — argv is built here.
        argv, cwd=cwd, env=environment, capture_output=True, text=True, check=False
    )
    assert completed.returncode == 0, f"{argv}:\n{completed.stdout}\n{completed.stderr}"
    return completed.stdout


@pytest.mark.parametrize(
    ("options", "commands"),
    [
        ((), (("app:hello", "Ada"), ("debug:bundles",))),
        (("--webapp",), (("app:hello",), ("debug:router",), ("debug:bundles",))),
    ],
)
def test_a_scaffolded_project_runs_and_checks_clean(
    tmp_path: Path, options: tuple[str, ...], commands: tuple[tuple[str, ...], ...]
) -> None:
    webapp = "--webapp" in options
    project = tmp_path / ("web-app" if webapp else "cli-app")

    _ = _run(
        (
            "uv",
            "run",
            "xtr",
            "new",
            str(project),
            *options,
            f"--local-packages={_PACKAGES}",
        ),
        _PACKAGES / "xtr-cli",
    )

    for check in _CHECKS:
        _ = _run(check, project)
    for command in commands:
        _ = _run(("uv", "run", project.name, *command), project)
    if webapp:
        served = _run(
            ("uv", "run", "xtr", "serve", f"--project-dir={project}", "--dry-run", "-n"),
            _PACKAGES / "xtr-cli",
        )
        assert f"WEB_RELOAD=1 uv run {project.name}-web" in served

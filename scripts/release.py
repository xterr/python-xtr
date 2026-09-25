# /// script
# requires-python = ">=3.11"
# ///
"""Keep the workspace and every package on one version.

All packages are released together, at one version, tagged ``X.Y.Z``. A package
classified ``Private :: Do Not Upload`` moves with the rest but is never
published or split.

    uv run scripts/release.py check [X.Y.Z]   # every package is on one version (and it is X.Y.Z)
    uv run scripts/release.py bump X.Y.Z      # move every package, rewrite sibling ranges, relock
    uv run scripts/release.py packages        # publishable packages, as JSON
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRIVATE = "Private :: Do Not Upload"
VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
REQUIREMENT_NAME = re.compile(r"^[A-Za-z0-9._-]+")


@dataclass(frozen=True, slots=True)
class Package:
    name: str
    version: str
    publishable: bool
    pyproject: Path


def packages() -> list[Package]:
    found: list[Package] = []
    for pyproject in sorted(ROOT.glob("packages/*/pyproject.toml")):
        project = tomllib.loads(pyproject.read_text())["project"]
        found.append(
            Package(
                name=project["name"],
                version=project["version"],
                publishable=PRIVATE not in project.get("classifiers", []),
                pyproject=pyproject,
            )
        )
    return found


def workspace_version() -> str:
    return tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]


def check(expected: str | None) -> None:
    versions = {package.version for package in packages()} | {workspace_version()}
    if len(versions) != 1:
        found = ", ".join(f"{p.name} {p.version}" for p in packages())
        sys.exit(f"not on one version: workspace {workspace_version()}, {found}")
    version = versions.pop()
    if expected is not None and expected != version:
        sys.exit(f"cannot release {expected}: the packages are at {version}")
    print(version)


def requirements(pyproject: Path) -> list[str]:
    data = tomllib.loads(pyproject.read_text())
    project = data["project"]
    found: list[str] = list(project.get("dependencies", []))
    for extra in project.get("optional-dependencies", {}).values():
        found.extend(extra)
    for group in data.get("dependency-groups", {}).values():
        found.extend(entry for entry in group if isinstance(entry, str))
    return found


def rewrite_ranges(major: int) -> None:
    """Point every requirement on a sibling at ``major``."""
    siblings = {package.name for package in packages()}
    for package in packages():
        text = package.pyproject.read_text()
        for requirement in requirements(package.pyproject):
            name = REQUIREMENT_NAME.match(requirement)
            if name is None or name.group() not in siblings:
                continue
            rest = requirement[name.end() :]
            extras = rest[: rest.index("]") + 1] if rest.startswith("[") else ""
            marker = rest[rest.index(";") :] if ";" in rest else ""
            ranged = f"{name.group()}{extras}>={major}.0,<{major + 1}{marker}"
            text = text.replace(f'"{requirement}"', f'"{ranged}"')
        package.pyproject.write_text(text)


def bump(version: str) -> None:
    matched = VERSION.match(version)
    if matched is None:
        sys.exit(f"not a X.Y.Z version: {version}")
    subprocess.run(["uv", "version", version, "--frozen"], cwd=ROOT, check=True)
    for package in packages():
        subprocess.run(
            ["uv", "version", "--package", package.name, version, "--frozen"],
            cwd=ROOT,
            check=True,
        )
    rewrite_ranges(int(matched.group(1)))
    subprocess.run(["uv", "lock"], cwd=ROOT, check=True)


def main(argv: list[str]) -> None:
    match argv:
        case ["check"]:
            check(None)
        case ["check", version]:
            check(version)
        case ["bump", version]:
            bump(version)
        case ["packages"]:
            print(json.dumps([p.name for p in packages() if p.publishable]))
        case _:
            sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])

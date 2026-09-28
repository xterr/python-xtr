# /// script
# requires-python = ">=3.11"
# ///
"""Keep the workspace and every package on one version.

All packages are released together, at one version, tagged ``X.Y.Z``. A package
classified ``Private :: Do Not Upload`` moves with the rest but is never
published or split.

    uv run scripts/release.py check [X.Y.Z]   # every package and the README on one version
    uv run scripts/release.py bump X.Y.Z      # move everything, rewrite ranges, relock

The README's package template and release commands name the current version and
major range, so a package created from it starts on the shared version.
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
README = ROOT / "README.md"
README_VERSION = re.compile(
    r'(version = "|release\.py bump |"bump: |git tag |push origin |read-only repository `)'
    r"\d+\.\d+\.\d+"
)
README_RANGE = re.compile(r"(xtr-[a-z-]+>=)\d+\.0,<\d+")


@dataclass(frozen=True, slots=True)
class Package:
    """A package of the workspace, as its manifest describes it."""

    name: str
    version: str
    publishable: bool
    pyproject: Path


def packages() -> list[Package]:
    """Return every package under ``packages/``, in name order."""
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


def examples() -> list[Path]:
    """Return the example applications' directories; they move with the packages."""
    return sorted(pyproject.parent for pyproject in ROOT.glob("examples/*/pyproject.toml"))


def example_version(directory: Path) -> str:
    """Return the version an example application is at."""
    return tomllib.loads((directory / "pyproject.toml").read_text())["project"]["version"]


def workspace_version() -> str:
    """Return the version of the workspace itself."""
    return tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]


def synced_readme(text: str, version: str) -> str:
    """Return the README with its template and release commands on ``version``."""
    major = int(version.split(".", maxsplit=1)[0])
    text = README_VERSION.sub(lambda m: f"{m.group(1)}{version}", text)
    return README_RANGE.sub(lambda m: f"{m.group(1)}{major}.0,<{major + 1}", text)


def check(expected: str | None) -> None:
    """Print the one version everything is on, or exit naming what is not on it."""
    versions = {package.version for package in packages()} | {workspace_version()}
    versions |= {example_version(example) for example in examples()}
    if len(versions) != 1:
        found = ", ".join(
            [f"{p.name} {p.version}" for p in packages()]
            + [f"{e.relative_to(ROOT)} {example_version(e)}" for e in examples()]
        )
        sys.exit(f"not on one version: workspace {workspace_version()}, {found}")
    version = versions.pop()
    if expected is not None and expected != version:
        sys.exit(f"cannot release {expected}: the packages are at {version}")
    text = README.read_text()
    if synced_readme(text, version) != text:
        sys.exit(f"README.md is not on {version}: run `uv run scripts/release.py bump {version}`")
    print(version)


def requirements(pyproject: Path) -> list[str]:
    """Return every requirement of a manifest: dependencies, extras and dependency groups."""
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
            closing = rest.find("]")
            if rest.startswith("[") and closing == -1:
                sys.exit(f"{package.pyproject}: unclosed extras in requirement {requirement!r}")
            extras = rest[: closing + 1] if rest.startswith("[") else ""
            marker = rest[rest.index(";") :] if ";" in rest else ""
            ranged = f"{name.group()}{extras}>={major}.0,<{major + 1}{marker}"
            # Whole quoted entries only, so one requirement never rewrites part of another.
            quoted = re.compile(rf'(?<="){re.escape(requirement)}(?=")')
            text = quoted.sub(ranged.replace("\\", "\\\\"), text)
        _ = package.pyproject.write_text(text)


def bump(version: str) -> None:
    """Move the workspace, every package and the README to ``version``, and relock."""
    matched = VERSION.match(version)
    if matched is None:
        sys.exit(f"not a X.Y.Z version: {version}")
    _ = subprocess.run(["uv", "version", version, "--frozen"], cwd=ROOT, check=True)
    for package in packages():
        _ = subprocess.run(
            ["uv", "version", "--package", package.name, version, "--frozen"],
            cwd=ROOT,
            check=True,
        )
    rewrite_ranges(int(matched.group(1)))
    _ = README.write_text(synced_readme(README.read_text(), version))
    _ = subprocess.run(["uv", "lock"], cwd=ROOT, check=True)
    for example in examples():
        # An example is a project of its own, with its own lockfile.
        _ = subprocess.run(["uv", "version", version, "--frozen"], cwd=example, check=True)
        _ = subprocess.run(["uv", "lock"], cwd=example, check=True)


def main(argv: list[str]) -> None:
    """Run the command ``argv`` names."""
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

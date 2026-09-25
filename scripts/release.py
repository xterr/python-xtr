# /// script
# requires-python = ">=3.11"
# ///
"""Keep each release group on one version, Symfony-style.

Every package belongs to a group by name: ``*-contracts`` packages are the
``contracts`` group, the rest are ``libraries``. A group is always released
together, at one version. A package classified ``Private :: Do Not Upload``
moves with its group but is never published or split.

    uv run scripts/release.py check              # each group is on one version
    uv run scripts/release.py bump GROUP X.Y.Z   # move a group, rewrite sibling ranges, relock
    uv run scripts/release.py packages [GROUP]   # publishable packages, as JSON
    uv run scripts/release.py tag TAG            # what a tag releases, as JSON

Tags: ``vX.Y.Z`` releases the libraries, ``contracts-vX.Y.Z`` the contracts.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, get_args

Group = Literal["libraries", "contracts"]

ROOT = Path(__file__).resolve().parent.parent
PRIVATE = "Private :: Do Not Upload"
VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
TAG = re.compile(r"^(?P<prefix>contracts-)?v(?P<version>\d+\.\d+\.\d+)$")
REQUIREMENT_NAME = re.compile(r"^[A-Za-z0-9._-]+")


@dataclass(frozen=True, slots=True)
class Package:
    name: str
    version: str
    publishable: bool
    pyproject: Path

    @property
    def group(self) -> Group:
        return "contracts" if self.name.endswith("-contracts") else "libraries"


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


def members(group: Group) -> list[Package]:
    return [package for package in packages() if package.group == group]


def group_version(group: Group) -> str:
    versions = {package.version for package in members(group)}
    if len(versions) != 1:
        found = ", ".join(f"{p.name} {p.version}" for p in members(group))
        sys.exit(f"{group} are not on one version: {found}")
    return versions.pop()


def check() -> None:
    for group in get_args(Group):
        print(f"{group}: {group_version(group)}")


def requirements(pyproject: Path) -> list[str]:
    data = tomllib.loads(pyproject.read_text())
    project = data["project"]
    found: list[str] = list(project.get("dependencies", []))
    for extra in project.get("optional-dependencies", {}).values():
        found.extend(extra)
    for group in data.get("dependency-groups", {}).values():
        found.extend(entry for entry in group if isinstance(entry, str))
    return found


def rewrite_ranges(group: Group, major: int) -> None:
    """Point every requirement on a member of ``group`` at ``major``."""
    siblings = {package.name for package in members(group)}
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


def bump(group: Group, version: str) -> None:
    matched = VERSION.match(version)
    if matched is None:
        sys.exit(f"not a X.Y.Z version: {version}")
    for package in members(group):
        subprocess.run(
            ["uv", "version", "--package", package.name, version, "--frozen"],
            cwd=ROOT,
            check=True,
        )
    rewrite_ranges(group, int(matched.group(1)))
    subprocess.run(["uv", "lock"], cwd=ROOT, check=True)


def publishable(group: Group | None) -> list[str]:
    return [p.name for p in packages() if p.publishable and group in (None, p.group)]


def tag(name: str) -> None:
    matched = TAG.match(name)
    if matched is None:
        sys.exit(f"not a release tag (vX.Y.Z or contracts-vX.Y.Z): {name}")
    group: Group = "contracts" if matched["prefix"] else "libraries"
    version = group_version(group)
    if version != matched["version"]:
        sys.exit(f"{name} does not match {group} at {version}")
    print(
        json.dumps({"group": group, "version": version, "packages": publishable(group)})
    )


def parse_group(value: str) -> Group:
    match value:
        case "libraries" | "contracts":
            return value
        case _:
            sys.exit(
                f"unknown group {value!r}: expected one of {', '.join(get_args(Group))}"
            )


def main(argv: list[str]) -> None:
    match argv:
        case ["check"]:
            check()
        case ["bump", group, version]:
            bump(parse_group(group), version)
        case ["packages"]:
            print(json.dumps(publishable(None)))
        case ["packages", group]:
            print(json.dumps(publishable(parse_group(group))))
        case ["tag", name]:
            tag(name)
        case _:
            sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])

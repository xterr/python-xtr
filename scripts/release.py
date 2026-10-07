# /// script
# requires-python = ">=3.11"
# ///
"""Keep the workspace, every package and every doc on one version.

All packages are released together, at one version, tagged ``X.Y.Z``. A package
classified ``Private :: Do Not Upload`` moves with the rest but is never
published or split.

    uv run scripts/release.py check [X.Y.Z]   # every package and every doc on one version
    uv run scripts/release.py bump X.Y.Z      # move everything, rewrite ranges, relock

The root README's package template and release commands name the current version,
and the READMEs and shipped skills quote the sibling ranges an application
installs, so a package created from the template starts on the shared version and
no doc offers a range that no longer exists.
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
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

ROOT = Path(__file__).resolve().parent.parent
PRIVATE = "Private :: Do Not Upload"
VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
REQUIREMENT_NAME = re.compile(r"^[A-Za-z0-9._-]+")
README = ROOT / "README.md"
README_VERSION = re.compile(
    r'(version = "|release\.py bump |"bump: |git tag |push origin |read-only repository `)'
    r"\d+\.\d+\.\d+"
)
DOC_RANGE = re.compile(r"(xtr-[a-z-]+(?:\[[a-z,]+\])?>=)\d+\.0,<\d+")


@dataclass(frozen=True, slots=True)
class Package:
    """A package of the workspace, as its manifest describes it, read once."""

    name: str
    version: str
    publishable: bool
    pyproject: Path
    text: str
    requirements: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Write:
    """A file a bump must rewrite, and the text to put in it."""

    path: Path
    text: str


def requirements(data: dict[str, Any]) -> tuple[str, ...]:
    """Return every requirement of a manifest: dependencies, extras and dependency groups."""
    project = data["project"]
    found: list[str] = list(project.get("dependencies", []))
    for extra in project.get("optional-dependencies", {}).values():
        found.extend(extra)
    for group in data.get("dependency-groups", {}).values():
        found.extend(entry for entry in group if isinstance(entry, str))
    return tuple(found)


def packages() -> list[Package]:
    """Return every package under ``packages/``, in name order, each manifest read once."""
    found: list[Package] = []
    for pyproject in sorted(ROOT.glob("packages/*/pyproject.toml")):
        text = pyproject.read_text()
        data = tomllib.loads(text)
        project = data["project"]
        found.append(
            Package(
                name=project["name"],
                version=project["version"],
                publishable=PRIVATE not in project.get("classifiers", []),
                pyproject=pyproject,
                text=text,
                requirements=requirements(data),
            )
        )
    return found


def examples() -> list[Path]:
    """Return the example applications' directories; they move with the packages."""
    return sorted(pyproject.parent for pyproject in ROOT.glob("examples/*/pyproject.toml"))


def example_versions() -> dict[Path, str]:
    """Return each example application's directory mapped to the version it is at."""
    return {
        directory: tomllib.loads((directory / "pyproject.toml").read_text())["project"]["version"]
        for directory in examples()
    }


def workspace_version() -> str:
    """Return the version of the workspace itself."""
    return tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]


def synced_ranges(text: str, major: int) -> str:
    """Return a doc with every sibling range it quotes on ``major``."""
    return DOC_RANGE.sub(lambda m: f"{m.group(1)}{major}.0,<{major + 1}", text)


def synced_readme(text: str, version: str) -> str:
    """Return the root README with its template and release commands on ``version``."""
    return synced_ranges(
        README_VERSION.sub(lambda m: f"{m.group(1)}{version}", text),
        int(version.split(".", maxsplit=1)[0]),
    )


def synced_docs(version: str) -> list[Write]:
    """Return every doc whose version literals are not on ``version`` yet.

    Only the root README carries the version itself; a package README and the
    skills beside it quote ranges, which follow the major. A skill ships inside
    the import package, at the version it describes, so its pages move with the
    README beside them.
    """
    major = int(version.split(".", maxsplit=1)[0])
    pages = [README, *sorted(ROOT.glob("packages/*/README.md"))]
    pages += sorted(ROOT.glob("packages/*/src/*/.agents/**/*.md"))
    planned: list[Write] = []
    for path in pages:
        text = path.read_text()
        wanted = synced_readme(text, version) if path == README else synced_ranges(text, major)
        if wanted != text:
            planned.append(Write(path, wanted))
    return planned


def sibling_range(requirement: str, name: str, major: int) -> str:
    """Return ``requirement`` ranged on ``major``, its extras and marker kept."""
    rest = requirement[len(name) :]
    extras = rest[: rest.find("]") + 1] if rest.startswith("[") else ""
    marker = rest[rest.index(";") :] if ";" in rest else ""
    return f"{name}{extras}>={major}.0,<{major + 1}{marker}"


def requoted(text: str, requirement: str, ranged: str) -> str:
    """Return ``text`` with every quoted ``requirement`` entry replaced by ``ranged``.

    Both TOML string styles are accepted, and only a whole quoted entry matches,
    so one requirement never rewrites part of another.
    """
    replacement = ranged.replace("\\", "\\\\")
    for quote in ('"', "'"):
        pattern = re.compile(rf"(?<={quote}){re.escape(requirement)}(?={quote})")
        text = pattern.sub(replacement, text)
    return text


def sibling_requirements(found: list[Package]) -> Iterator[tuple[Package, str, str]]:
    """Yield every requirement a package takes on a sibling, with the sibling's name.

    A requirement whose extras are left unclosed stops the run here, naming the
    manifest: every reader validates while nothing is written, so a bump is
    all-or-nothing.
    """
    siblings = {package.name for package in found}
    for package in found:
        for requirement in package.requirements:
            name = REQUIREMENT_NAME.match(requirement)
            if name is None or name.group() not in siblings:
                continue
            rest = requirement[name.end() :]
            if rest.startswith("[") and "]" not in rest:
                sys.exit(f"{package.pyproject}: unclosed extras in requirement {requirement!r}")
            yield package, requirement, name.group()


def stale_ranges(found: list[Package], major: int) -> list[str]:
    """Return every requirement on a sibling not ranged ``>={major}.0,<{major + 1}``."""
    wanted = f">={major}.0,<{major + 1}"
    stale: list[str] = []
    for package, requirement, name in sibling_requirements(found):
        rest = requirement[len(name) :].split(";", 1)[0].strip()
        if rest.startswith("["):
            rest = rest[rest.find("]") + 1 :]
        if rest != wanted:
            stale.append(f"{package.name} requires {name}{rest}")
    return stale


def ranged_manifests(found: list[Package], major: int) -> list[Write]:
    """Return every manifest whose requirements on a sibling must move to ``major``.

    Nothing is written here: a requirement the script cannot read stops the whole
    bump while the tree is still untouched.
    """
    ranged = {package.pyproject: package.text for package in found}
    for package, requirement, name in sibling_requirements(found):
        ranged[package.pyproject] = requoted(
            ranged[package.pyproject], requirement, sibling_range(requirement, name, major)
        )
    return [
        Write(package.pyproject, ranged[package.pyproject])
        for package in found
        if ranged[package.pyproject] != package.text
    ]


def check(expected: str | None) -> None:
    """Print the one version everything is on, or exit naming what is not on it."""
    found = packages()
    workspace = workspace_version()
    at = example_versions()
    versions = {package.version for package in found} | {workspace} | set(at.values())
    if len(versions) != 1:
        listed = ", ".join(
            [f"{package.name} {package.version}" for package in found]
            + [f"{directory.relative_to(ROOT)} {version}" for directory, version in at.items()]
        )
        sys.exit(f"not on one version: workspace {workspace}, {listed}")
    version = versions.pop()
    stale = stale_ranges(found, int(version.split(".", maxsplit=1)[0]))
    if stale:
        sys.exit(f"ranges not on {version}'s major: {', '.join(stale)}")
    if expected is not None and expected != version:
        sys.exit(f"cannot release {expected}: the packages are at {version}")
    behind = [str(write.path.relative_to(ROOT)) for write in synced_docs(version)]
    if behind:
        sys.exit(
            f"not on {version}: {', '.join(behind)}; run `uv run scripts/release.py bump {version}`"
        )
    print(version)


def recovery(found: list[Package], writes: list[Write]) -> str:
    """Return the git pathspec covering everything a bump can leave half-moved."""
    touched = {write.path for write in writes}
    touched |= {package.pyproject for package in found}
    touched |= {ROOT / "pyproject.toml", ROOT / "uv.lock"}
    for example in examples():
        touched |= {example / "pyproject.toml", example / "uv.lock"}
    return " ".join(sorted(str(path.relative_to(ROOT)) for path in touched))


def move_versions(found: list[Package], version: str) -> None:
    """Put the workspace, every package and every example on ``version``, and relock."""
    _ = subprocess.run(["uv", "version", version, "--frozen"], cwd=ROOT, check=True)
    for package in found:
        _ = subprocess.run(
            ["uv", "version", "--package", package.name, version, "--frozen"],
            cwd=ROOT,
            check=True,
        )
    _ = subprocess.run(["uv", "lock"], cwd=ROOT, check=True)
    for example in examples():
        # An example is a project of its own, with its own lockfile.
        _ = subprocess.run(["uv", "version", version, "--frozen"], cwd=example, check=True)
        _ = subprocess.run(["uv", "lock"], cwd=example, check=True)


def bump(version: str) -> None:
    """Move the workspace, every package, every doc and the README to ``version``, and relock.

    Everything is read and planned first, so a manifest the script cannot rewrite
    stops the bump with the tree untouched. The ranges and docs are written before
    ``uv version`` moves the versions, because ``uv`` rewrites the same manifests.
    """
    matched = VERSION.match(version)
    if matched is None:
        sys.exit(f"not a X.Y.Z version: {version}")
    found = packages()
    writes = ranged_manifests(found, int(matched.group(1))) + synced_docs(version)
    try:
        for write in writes:
            _ = write.path.write_text(write.text)
        move_versions(found, version)
    except (OSError, subprocess.CalledProcessError) as error:
        sys.exit(
            f"bump {version} stopped: {error}\nto undo: git restore -- {recovery(found, writes)}"
        )


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

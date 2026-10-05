"""Every agent skill a package ships is one an installer will accept and an agent can follow.

A package is not required to ship a skill; only the skills that exist are checked. The rules are
the ones skill installers apply when they read a package's ``.agents/skills`` directory, plus the
repository's own naming rules.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_SKILLS = sorted(_ROOT.glob("packages/*/src/*/.agents/skills/*/SKILL.md"))

_NAME = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
_LINK = re.compile(r"\]\(([^)\s]+)\)")
_MAX_DESCRIPTION = 1024


def _frontmatter(skill: Path) -> dict[str, str]:
    lines = skill.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "---", f"{skill}: must open with YAML frontmatter"
    end = lines.index("---", 1)
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def _id(skill: Path) -> str:
    return skill.parent.name


def test_skills_are_found() -> None:
    assert _SKILLS


@pytest.mark.parametrize("skill", _SKILLS, ids=_id)
def test_name_matches_its_directory_and_package(skill: Path) -> None:
    name = _frontmatter(skill).get("name", "")
    distribution = skill.parents[5].name

    assert _NAME.fullmatch(name)
    assert "--" not in name
    assert name == skill.parent.name
    assert name == distribution or name.startswith(f"{distribution}-")


@pytest.mark.parametrize("skill", _SKILLS, ids=_id)
def test_description_says_when_to_use_it(skill: Path) -> None:
    description = _frontmatter(skill).get("description", "")

    assert description
    assert len(description) <= _MAX_DESCRIPTION
    # An unquoted YAML value may not contain ": " or " #"; installers reject the whole file.
    assert ": " not in description
    assert " #" not in description
    assert "Use when" in description


@pytest.mark.parametrize("skill", _SKILLS, ids=_id)
def test_relative_links_resolve(skill: Path) -> None:
    for page in sorted(skill.parent.rglob("*.md")):
        for target in _LINK.findall(page.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            assert (page.parent / target.split("#")[0]).exists(), f"{page}: {target}"

"""Every link a tracked Markdown page writes resolves.

The pages are the ones git tracks; drafts under ``.omo/`` are left out. A page is read the
way GitHub renders it, so a fenced code block holds examples rather than links: neither its
links nor its headings count. A relative target must exist on disk, and an ``#anchor`` must
name a heading of the page it points at, slugged the way GitHub slugs one - lowercased,
punctuation dropped, each space turned into a dash, and a repeated slug numbered ``-1``,
``-2``.
"""

from __future__ import annotations

import re
import subprocess
from collections import Counter
from functools import cache
from pathlib import Path
from urllib.parse import unquote

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_DRAFTS = ".omo"

_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_HEADING = re.compile(r"^ {0,3}#{1,6}(?: +(.*?))?(?: +#+)? *$")
_LINK = re.compile(r"\]\(\s*<?([^()<>\s]+?)>?\s*\)")
# A target with a scheme, or a protocol-relative one, is somebody else's to serve.
_ELSEWHERE = re.compile(r"^(?:[A-Za-z][A-Za-z0-9+.\-]*:|//)")
_LINK_TEXT = re.compile(r"!?\[([^\]]*)\]\([^()]*\)")
_PUNCTUATION = re.compile(r"[^\w\- ]")
# GitHub answers ``#L12`` and ``#L12-L20`` on any file it shows, not only Markdown.
_LINE_RANGE = re.compile(r"^L\d+(?:-L\d+)?$")


def _tracked_pages() -> list[Path]:
    """Return every Markdown page git tracks, drafts aside, in path order."""
    listed = subprocess.run(
        ["git", "ls-files", "-z", "*.md"],
        cwd=_ROOT,
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    return sorted(
        _ROOT / name for name in listed.split("\0") if name and _DRAFTS not in Path(name).parts
    )


def _closes(marker: str, fence: str) -> bool:
    """Tell whether a fence marker closes the one that opened the block."""
    return marker[0] == fence[0] and len(marker) >= len(fence)


def _rendered_lines(page: Path) -> list[tuple[int, str]]:
    """Return the page's lines outside fenced code blocks, numbered from one."""
    kept: list[tuple[int, str]] = []
    fence: str | None = None
    for number, line in enumerate(page.read_text(encoding="utf-8").splitlines(), start=1):
        marker = _FENCE.match(line)
        if fence is None:
            if marker is None:
                kept.append((number, line))
            else:
                fence = marker.group(1)
        elif marker is not None and _closes(marker.group(1), fence):
            fence = None
    return kept


def _slug(heading: str) -> str:
    """Return the anchor GitHub gives a heading."""
    text = _LINK_TEXT.sub(r"\1", heading.strip())
    return _PUNCTUATION.sub("", text.lower()).replace(" ", "-")


@cache
def _anchors(page: Path) -> frozenset[str]:
    """Return every anchor the page's headings answer to."""
    seen: Counter[str] = Counter()
    found: set[str] = set()
    for _, line in _rendered_lines(page):
        matched = _HEADING.match(line)
        heading = (matched.group(1) or "").strip() if matched is not None else ""
        if not heading:
            continue
        slug = _slug(heading)
        found.add(f"{slug}-{seen[slug]}" if seen[slug] else slug)
        seen[slug] += 1
    return frozenset(found)


def _unresolved(page: Path, target: str) -> str | None:
    """Return why ``target`` does not resolve from ``page``, or ``None`` when it does."""
    path, _, anchor = target.partition("#")
    destination = (page.parent / unquote(path)).resolve() if path else page
    if path and not destination.exists():
        return "no such path"
    if not anchor or _LINE_RANGE.match(anchor):
        return None
    # A link to a directory lands on the README GitHub renders under it.
    document = destination / "README.md" if destination.is_dir() else destination
    if document.suffix != ".md" or not document.is_file():
        return "an anchor on something that has no headings"
    if unquote(anchor) not in _anchors(document):
        return "no such heading"
    return None


def _broken_links(page: Path) -> list[str]:
    """Return one line per link of ``page`` that does not resolve, with the reason."""
    broken: list[str] = []
    for number, line in _rendered_lines(page):
        for target in _LINK.findall(line):
            if _ELSEWHERE.match(target):
                continue
            reason = _unresolved(page, target)
            if reason is not None:
                broken.append(f"line {number}: {target} - {reason}")
    return broken


_PAGES = _tracked_pages()


def _id(page: Path) -> str:
    return str(page.relative_to(_ROOT))


def test_pages_are_found() -> None:
    assert _PAGES


@pytest.mark.parametrize("page", _PAGES, ids=_id)
def test_every_link_resolves(page: Path) -> None:
    broken = _broken_links(page)

    assert broken == [], f"{page.relative_to(_ROOT)}\n" + "\n".join(broken)


@pytest.mark.parametrize(
    ("heading", "anchor"),
    [
        ("Use in an application", "use-in-an-application"),
        ("Kernel / bundle", "kernel--bundle"),
        ("Why?", "why"),
        ("`pyproject.toml`", "pyprojecttoml"),
        ("**Bold** and _kept_", "bold-and-_kept_"),
        ("See [AGENTS.md](AGENTS.md)", "see-agentsmd"),
    ],
)
def test_a_heading_becomes_the_anchor_github_gives_it(heading: str, anchor: str) -> None:
    assert _slug(heading) == anchor


def test_a_repeated_heading_is_numbered(tmp_path: Path) -> None:
    page = tmp_path / "repeated.md"
    _ = page.write_text("## Errors\n\n## Errors\n\n## Errors\n", encoding="utf-8")

    assert _anchors(page) == frozenset({"errors", "errors-1", "errors-2"})


def test_a_missing_path_is_reported(tmp_path: Path) -> None:
    page = tmp_path / "missing_path.md"
    _ = page.write_text("[gone](nowhere.md)\n", encoding="utf-8")

    assert _broken_links(page) == ["line 1: nowhere.md - no such path"]


def test_a_missing_heading_is_reported(tmp_path: Path) -> None:
    page = tmp_path / "missing_heading.md"
    _ = page.write_text("## Errors\n\n[gone](#warnings)\n", encoding="utf-8")

    assert _broken_links(page) == ["line 3: #warnings - no such heading"]


def test_a_fenced_block_holds_examples_rather_than_links(tmp_path: Path) -> None:
    page = tmp_path / "fenced.md"
    _ = page.write_text(
        "````markdown\n```\n## Example\n```\n[template](nowhere.md)\n````\n\n[here](#example)\n",
        encoding="utf-8",
    )

    assert _broken_links(page) == ["line 8: #example - no such heading"]

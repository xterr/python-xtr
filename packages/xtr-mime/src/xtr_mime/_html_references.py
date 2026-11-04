"""Finds the names an HTML body refers to through ``cid:``, in one pass over it.

An image's source, or any element's background, is read as a reference when it is
``cid:<name>``: quoted, the name runs to the closing quote on its line, past the end of the tag
if need be; unquoted, to the end of the tag or the next space. In a tag, the last such
attribute before its ``>`` is the one read, and the search goes on after it.

A tag left open runs to the next ``>``. Looking for its last attribute again from each tag
opened before that ``>`` would read the run once per tag: on a megabyte of ``<a `` it takes
minutes. The places a reference starts are found once, so each run is read once.
"""

from __future__ import annotations

import re
from bisect import bisect_left
from dataclasses import dataclass
from typing import Final

__all__ = ["referenced_names"]


@dataclass(frozen=True, slots=True)
class _Search:
    """A tag to look in, and the attribute of it that refers to a part."""

    tag: re.Pattern[str]
    reference: re.Pattern[str]
    # Where a reference starts. A bare name is only checked to be there: matching it whole
    # from each place would read on to its end once per place.
    start: re.Pattern[str]


def _search(tag: str, attribute: str) -> _Search:
    flags = re.IGNORECASE | re.ASCII
    return _Search(
        re.compile(tag, flags),
        re.compile(rf"""{attribute}\s*=\s*(?:(['"])cid:(.+?)\1|cid:([^>\s]+))""", flags),
        re.compile(rf"""{attribute}(?=\s*=\s*(?:(['"])cid:.+?\1|cid:[^>\s]))""", flags),
    )


_SEARCHES: Final = (_search(r"<img\s+", "src"), _search(r"<\w+\s+", "background"))


def referenced_names(html: str) -> list[str]:
    """Return the names ``html`` refers to, each once: quoted ones, then bare ones, per search."""
    names: dict[str, None] = {}
    for search in _SEARCHES:
        found = _references(html, search)
        quoted = [str(match[2] or "") for match in found]
        bare = [str(match[3] or "") for match in found]
        names.update(dict.fromkeys(name for name in [*quoted, *bare] if name))
    return list(names)


def _references(html: str, search: _Search) -> list[re.Match[str]]:
    """Return the last reference of each tag that has one, in the order the tags open."""
    starts = [match.start() for match in search.start.finditer(html)]
    found: list[re.Match[str]] = []
    position = 0
    tag_end = -1
    while (opening := search.tag.search(html, position)) is not None:
        attributes = opening.end()
        if attributes > tag_end:
            tag_end = html.find(">", attributes)
            if tag_end < 0:
                tag_end = len(html)
        last = bisect_left(starts, tag_end) - 1
        match = None
        if last >= 0 and starts[last] >= attributes:
            match = search.reference.match(html, starts[last])
        if match is None:
            # Every other tag opened before this ">" has fewer attributes to look in.
            position = tag_end
        else:
            found.append(match)
            position = match.end()
    return found

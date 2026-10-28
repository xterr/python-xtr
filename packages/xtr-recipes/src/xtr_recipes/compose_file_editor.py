"""ComposeFileEditor: the blocks one package owns under the top-level keys of a Compose file."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, final

from .exception import MarkedBlockError

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = ["ComposeFileEditor"]

# A top-level key standing alone on its line: `services:`, `"volumes":`.
_TOP_LEVEL_KEY = re.compile(r"""^['"]?(?P<key>[A-Za-z0-9_-]+)['"]?:\s*$""")


@final
class ComposeFileEditor:
    """Reads and rewrites the blocks one package owns in a ``compose.yaml``.

    A Compose file is one mapping, so a package cannot own a stretch of it the
    way it owns a block of ``.env``: what it brings goes under keys every
    package shares. Each of its contributions is a block of its own, between
    the markers naming its distribution, placed at the end of the top-level key
    it belongs under::

        services:
        ###> xtr-orm ###
          database:
            image: postgres:16-alpine
        ###< xtr-orm ###

        volumes:
        ###> xtr-orm ###
          database_data:
        ###< xtr-orm ###

    The markers are comments, so the file stays valid YAML. A missing key is
    added at the end of the file. A block is rewritten where it stands, so a
    service the owner added after it is not moved. The blocks are indented the
    way the file already is, so they sit beside services written at four
    spaces as well as at two. Removal takes the blocks out, and a key left with
    nothing under it goes with them; a file left with nothing reads as empty.

    Stateless: every method takes a file's whole text and returns the new one.
    """

    __slots__ = ()

    def has_blocks(self, text: str, package: str) -> bool:
        """Whether ``text`` holds any block of ``package``'s.

        Raises:
            MarkedBlockError: When one of the package's blocks is opened and
                never closed.
        """
        return bool(_blocks(text.splitlines(), package))

    def put_blocks(self, text: str, package: str, sections: Mapping[str, Sequence[str]]) -> str:
        """Return ``text`` with ``package`` owning exactly ``sections``.

        Args:
            text: The Compose file's whole text.
            package: The distribution the blocks belong to.
            sections: Each top-level key mapped to the YAML lines that go under
                it; no sections clears every block the package has.

        Returns:
            The new text, ending in a newline, or empty when nothing is left.

        Raises:
            MarkedBlockError: When one of the package's blocks is opened and
                never closed.
        """
        lines = text.splitlines()
        unit = _indent_unit(lines, package)
        stale = {key for key, _, _ in _blocks(lines, package) if key not in sections}
        lines = _remove(lines, package, stale)
        for key, body in sections.items():
            lines = _put(lines, package, key, _reindented(body, unit))
        return _joined(lines)


def _markers(package: str) -> tuple[str, str]:
    """Return the opening and closing marker of ``package``'s blocks."""
    return f"###> {package} ###", f"###< {package} ###"


def _is_top_level(line: str) -> bool:
    """Whether ``line`` starts a new top-level entry, ending the one before it."""
    return bool(line.strip()) and not line[0].isspace() and not line.startswith("#")


def _blocks(lines: Sequence[str], package: str) -> list[tuple[str | None, int, int]]:
    """Return each of ``package``'s blocks as its key and the indices of its markers.

    Raises:
        MarkedBlockError: When an opening marker is never closed; where the
            block ends is then unknown, and rewriting it would take the rest of
            the file with it.
    """
    opening, closing = _markers(package)
    found: list[tuple[str | None, int, int]] = []
    key: str | None = None
    start: int | None = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if start is not None:
            if stripped == closing:
                found.append((key, start, index))
                start = None
            continue
        if stripped == opening:
            start = index
        elif _is_top_level(line):
            match = _TOP_LEVEL_KEY.match(line)
            key = match.group("key") if match is not None else None
    if start is not None:
        raise MarkedBlockError(package, f"{opening!r} is never closed by {closing!r}")
    return found


def _section(lines: Sequence[str], key: str) -> tuple[int, int] | None:
    """Return the index of ``key``'s line and the end of what lies under it."""
    for index, line in enumerate(lines):
        match = _TOP_LEVEL_KEY.match(line)
        if match is not None and match.group("key") == key:
            end = next(
                (after for after in range(index + 1, len(lines)) if _is_top_level(lines[after])),
                len(lines),
            )
            return index, end
    return None


def _put(lines: list[str], package: str, key: str, body: Sequence[str]) -> list[str]:
    """Return ``lines`` with ``package``'s block under ``key`` holding ``body``."""
    opening, closing = _markers(package)
    block = [opening, *body, closing]
    for owner, start, end in _blocks(lines, package):
        if owner == key:
            return [*lines[:start], *block, *lines[end + 1 :]]
    section = _section(lines, key)
    if section is None:
        before = _without_trailing_blanks(lines)
        return [*before, *([""] if before else []), f"{key}:", *block]
    line, end = section
    position = end
    while position > line + 1 and not lines[position - 1].strip():
        position -= 1
    # A block after someone else's entries is set apart from them by a blank line.
    gap = [""] if position > line + 1 else []
    return [*lines[:position], *gap, *block, *lines[position:]]


def _remove(lines: list[str], package: str, keys: set[str | None]) -> list[str]:
    """Return ``lines`` without ``package``'s blocks under ``keys``.

    The blank line that set a block apart goes with it, and a key left with
    nothing under it is removed too: the recipe added it, and an empty
    ``volumes:`` reads as a mistake.
    """
    for key, start, end in reversed(_blocks(lines, package)):
        if key not in keys:
            continue
        before, after = lines[:start], lines[end + 1 :]
        if before and not before[-1].strip():
            before = before[:-1]
        elif after and not after[0].strip():
            after = after[1:]
        lines = [*before, *after]
        if key is not None:
            lines = _without_empty_section(lines, key)
    return lines


def _without_empty_section(lines: list[str], key: str) -> list[str]:
    """Return ``lines`` without ``key`` when nothing but blank lines lies under it."""
    section = _section(lines, key)
    if section is None:
        return lines
    line, end = section
    if any(each.strip() for each in lines[line + 1 : end]):
        return lines
    before = _without_trailing_blanks(lines[:line])
    after = lines[end:]
    return [*before, *([""] if before and after else []), *after]


def _indent_unit(lines: Sequence[str], package: str) -> int | None:
    """Return the smallest indentation the file's own entries use, or ``None`` for none."""
    owned = {index for _, start, end in _blocks(lines, package) for index in range(start, end + 1)}
    widths = [
        _width(line)
        for index, line in enumerate(lines)
        if index not in owned and line.strip() and not line.lstrip().startswith("#")
    ]
    return min((width for width in widths if width), default=None)


def _reindented(body: Sequence[str], unit: int | None) -> tuple[str, ...]:
    """Return ``body`` indented in steps of ``unit``, in place of its own steps."""
    own = min((_width(line) for line in body if line.strip() and _width(line)), default=0)
    if unit is None or not own or own == unit:
        return tuple(body)
    return tuple(
        " " * (_width(line) // own * unit + _width(line) % own) + line.lstrip(" ") for line in body
    )


def _width(line: str) -> int:
    """Return how many spaces ``line`` is indented by."""
    return len(line) - len(line.lstrip(" "))


def _without_trailing_blanks(lines: Sequence[str]) -> list[str]:
    """Return ``lines`` with the blank lines at its end dropped."""
    kept = list(lines)
    while kept and not kept[-1].strip():
        _ = kept.pop()
    return kept


def _joined(lines: Sequence[str]) -> str:
    """Join ``lines`` into newline-ended text; nothing but blanks is no text."""
    kept = _without_trailing_blanks(lines)
    return "".join(f"{line}\n" for line in kept)

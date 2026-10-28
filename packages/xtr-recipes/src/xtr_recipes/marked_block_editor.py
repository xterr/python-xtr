"""MarkedBlockEditor: the block one package owns in a project's ``.env`` or ``.gitignore``."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, final

from .exception import MarkedBlockError
from .file_write import ENV_NAME, write_text

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence
    from pathlib import Path

__all__ = ["MarkedBlockEditor"]


@final
class MarkedBlockEditor:
    """Reads and rewrites the block one package owns in a line-oriented file.

    A recipe writes the environment variables and ignore lines it brings between
    two marker comments naming its distribution::

        ###> xtr-messenger ###
        MESSENGER_DSN=
        ###< xtr-messenger ###

    The markers are what makes undoing possible: removal deletes the block
    rather than guessing which lines were once written for the package.
    Everything outside the block belongs to the application owner — a key
    already set, an ignore line already there — and is adopted: left exactly
    where it is, never recorded, so it survives the package going away.

    A block an earlier release wrote between ``# >>> <package>`` and
    ``# <<< <package>`` is still read as the package's own, and is rewritten
    with the current markers the next time the block is written.

    Stateless: every method takes a file's whole text and returns the new one,
    with two helpers so a caller need not repeat the encoding.
    """

    __slots__ = ()

    def read(self, path: Path) -> str:
        """Return ``path``'s text, or the empty string when there is no such file."""
        if not path.is_file():
            return ""
        return path.read_text(encoding="utf-8")

    def write(self, path: Path, text: str) -> None:
        """Write ``text`` to ``path``, creating the directories above it."""
        write_text(path, text, private=path.name == ENV_NAME)

    def env_lines(self, text: str, package: str, entries: Mapping[str, str]) -> tuple[str, ...]:
        """Return the assignments to write for ``entries`` that ``text`` lacks.

        A key already assigned outside ``package``'s own block is the
        application owner's and is skipped — adopted, not recorded, so removing
        the package leaves it alone. A key commented out is not in the
        environment, so the recipe still has its line to contribute.

        Args:
            text: The ``.env`` file's whole text.
            package: The distribution whose block the keys would go in.
            entries: Each key mapped to its default; ``""`` means the recipe
                has no default to offer.

        Returns:
            One ``KEY=value`` line per key still to write, in ``entries``
            order, commented out as ``# KEY=`` where there is no default — an
            empty ``KEY=`` would set the variable to ``""`` and hide the error
            that says it was never configured. A key already assigned inside
            the package's own block keeps the line it has there: the owner
            filled the value in, and re-applying the recipe must not undo it.

        Raises:
            MarkedBlockError: When the package's block is opened and never
                closed.
        """
        inside = self.block_lines(text, package)
        lines: list[str] = []
        for key in self.env_keys(text, package, entries):
            filled = next((line for line in inside if _assigned((line,), key)), None)
            if filled is not None:
                lines.append(filled)
            else:
                lines.append(f"{key}={entries[key]}" if entries[key] else f"# {key}=")
        return tuple(lines)

    def env_keys(self, text: str, package: str, entries: Mapping[str, str]) -> tuple[str, ...]:
        """Return the keys :meth:`env_lines` would write, without their values.

        These are the keys the lock records, because they are the ones inside
        the package's own block: what is skipped as already set belongs to the
        application owner and must survive the package going away.

        Args:
            text: The ``.env`` file's whole text.
            package: The distribution whose block the keys would go in.
            entries: Each key mapped to its default, as in :meth:`env_lines`.

        Returns:
            The keys still to write, in ``entries`` order.

        Raises:
            MarkedBlockError: When the package's block is opened and never
                closed.
        """
        outside = _outside(text, package)
        return tuple(key for key in entries if not _assigned(outside, key))

    def env_value(self, text: str, key: str) -> str | None:
        """Return the value ``key`` is assigned in ``text``, or ``None`` when it is not.

        The last assignment wins, as it does when the file is loaded; a value
        wrapped in matching quotes is read without them.
        """
        assignment = _assignment(key)
        value: str | None = None
        for line in text.splitlines():
            match = assignment.match(line.lstrip())
            if match is not None:
                value = _unquoted(line.lstrip()[match.end() :].strip())
        return value

    def ignore_lines(self, text: str, package: str, lines: Iterable[str]) -> tuple[str, ...]:
        """Return the entries of ``lines`` that ``text`` does not already carry.

        Compared stripped and outside ``package``'s own block, so an ignore
        rule the application owner wrote by hand is adopted rather than
        repeated; a blank entry has nothing to ignore and is dropped.

        Raises:
            MarkedBlockError: When the package's block is opened and never
                closed.
        """
        present = {line.strip() for line in _outside(text, package) if line.strip()}
        chosen: list[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped and stripped not in present:
                present.add(stripped)
                chosen.append(stripped)
        return tuple(chosen)

    def block_lines(self, text: str, package: str) -> tuple[str, ...]:
        """Return what lies inside ``package``'s block, or ``()`` when it has none.

        Raises:
            MarkedBlockError: When the block is opened and never closed.
        """
        lines = text.splitlines()
        span = _span(lines, package)
        if span is None:
            return ()
        start, end = span
        return tuple(lines[start + 1 : end])

    def put_block(self, text: str, package: str, lines: Sequence[str]) -> str:
        """Return ``text`` with ``package``'s block holding exactly ``lines``.

        An existing block is replaced where it stands, so applying the same
        recipe twice leaves the file byte for byte the same; a new one is
        appended after a single blank line. No lines means the package
        contributes nothing, which is the same as having no block at all.

        Args:
            text: The file's whole text.
            package: The distribution the block belongs to.
            lines: What goes between the markers.

        Returns:
            The new text, ending in a newline.

        Raises:
            MarkedBlockError: When the block is opened and never closed.
        """
        if not lines:
            return self.remove_block(text, package)
        opening, closing = _markers(package)[0]
        block = [opening, *lines, closing]
        existing = text.splitlines()
        span = _span(existing, package)
        if span is not None:
            start, end = span
            return _joined([*existing[:start], *block, *existing[end + 1 :]])
        before = _without_trailing_blanks(existing)
        return _joined(block if not before else [*before, "", *block])

    def remove_block(self, text: str, package: str) -> str:
        """Return ``text`` without ``package``'s block, or unchanged when it has none.

        The blank line that separated the block from its neighbour goes with
        it, so a file a recipe once wrote into comes back as it was.

        Raises:
            MarkedBlockError: When the block is opened and never closed.
        """
        lines = text.splitlines()
        span = _span(lines, package)
        if span is None:
            return text
        start, end = span
        before, after = lines[:start], lines[end + 1 :]
        if before and not before[-1].strip():
            before = before[:-1]
        elif not before and after and not after[0].strip():
            after = after[1:]
        rest = [*before, *after]
        if not any(line.strip() for line in rest):
            return ""
        return _joined(rest)


def _span(lines: Sequence[str], package: str) -> tuple[int, int] | None:
    """Return the indices of ``package``'s two markers, or ``None`` for no block.

    The current markers are looked for first, then the ones an earlier release
    wrote, so a project synced before the markers changed keeps its block.

    Raises:
        MarkedBlockError: When the opening marker has no closing one; where the
            block ends is then unknown, and rewriting it would take the rest of
            the file with it.
    """
    for opening, closing in _markers(package):
        span = _marked(lines, package, opening, closing)
        if span is not None:
            return span
    return None


def _markers(package: str) -> tuple[tuple[str, str], ...]:
    """Return ``package``'s marker pairs: the one written now, then the earlier one."""
    return (
        (f"###> {package} ###", f"###< {package} ###"),
        (f"# >>> {package}", f"# <<< {package}"),
    )


def _marked(
    lines: Sequence[str],
    package: str,
    opening: str,
    closing: str,
) -> tuple[int, int] | None:
    """Return the indices of one marker pair in ``lines``, or ``None`` when it opens nowhere.

    Raises:
        MarkedBlockError: When ``opening`` is never closed by ``closing``.
    """
    start: int | None = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if start is None:
            if stripped == opening:
                start = index
        elif stripped == closing:
            return start, index
    if start is None:
        return None
    raise MarkedBlockError(package, f"{opening!r} is never closed by {closing!r}")


def _outside(text: str, package: str) -> tuple[str, ...]:
    """Return the lines of ``text`` that lie outside ``package``'s own block."""
    lines = text.splitlines()
    span = _span(lines, package)
    if span is None:
        return tuple(lines)
    start, end = span
    return (*lines[:start], *lines[end + 1 :])


def _assigned(lines: Iterable[str], key: str) -> bool:
    """Whether ``key`` is assigned on any of ``lines``, with or without ``export``.

    A commented ``# KEY=`` does not count: nothing reaches the environment from
    it, so the key is as good as missing.
    """
    assignment = _assignment(key)
    return any(assignment.match(line.lstrip()) for line in lines)


def _assignment(key: str) -> re.Pattern[str]:
    """Return the pattern of a line assigning ``key``, with or without ``export``."""
    return re.compile(rf"^(?:export\s+)?{re.escape(key)}\s*=")


def _unquoted(value: str) -> str:
    """Return ``value`` without one pair of matching surrounding quotes."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:  # noqa: PLR2004 — a pair of quotes is two characters.
        return value[1:-1]
    return value


def _without_trailing_blanks(lines: Sequence[str]) -> list[str]:
    """Return ``lines`` with the blank lines at its end dropped."""
    kept = list(lines)
    while kept and not kept[-1].strip():
        _ = kept.pop()
    return kept


def _joined(lines: Sequence[str]) -> str:
    """Join ``lines`` into text, each one newline-ended; no lines is no text."""
    return "".join(f"{line}\n" for line in lines)

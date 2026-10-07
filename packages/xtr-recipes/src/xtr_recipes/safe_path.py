"""Resolving a recorded path against the project, refusing one that escapes it."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from .exception import UnsafePathError

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["has_traversal", "within"]

# A separator on one of the platforms this runs on, a plain character to
# ``PurePosixPath``: a path holding one has two readings, so it has none.
_BACKSLASH = "\\"


def has_traversal(display: str) -> bool:
    r"""Whether ``display`` is absolute, climbs out of its own root, or is not ``/``-separated.

    A recipe records and declares paths relative to a known root, ``/``-
    separated. One that is absolute, or whose ``..`` segments climb above that
    root, would reach outside it — the test a manifest and the lock both apply
    before a path is ever joined to a directory.

    A backslash is an ordinary character here and a separator to the operating
    system that uses it, so ``..\..\x`` would pass as one harmless segment and
    climb two directories once joined. A path holding one is refused rather
    than read two ways.
    """
    if _BACKSLASH in display:
        return True
    pure = PurePosixPath(display)
    if pure.is_absolute():
        return True
    depth = 0
    for part in pure.parts:
        if part == "..":
            depth -= 1
            if depth < 0:
                return True
        elif part != ".":
            depth += 1
    return False


def within(project_dir: Path, display: str) -> Path:
    """Return ``display`` resolved under ``project_dir``, or refuse it.

    Args:
        project_dir: The directory every recorded path is relative to.
        display: A ``/``-separated relative path from a manifest or the lock.

    Returns:
        The absolute path it names inside the project.

    Raises:
        UnsafePathError: When ``display`` is absolute or resolves outside
            ``project_dir``.
    """
    if has_traversal(display):
        raise UnsafePathError(display, "resolves outside the project directory")
    root = project_dir.resolve()
    resolved = (root / display).resolve()
    if resolved != root and root not in resolved.parents:
        raise UnsafePathError(display, "resolves outside the project directory")
    return resolved

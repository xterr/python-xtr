"""Turning a caller's path into the plain form a backend can trust."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["PathNormalizerInterface"]


@runtime_checkable
class PathNormalizerInterface(Protocol):
    """Resolves a caller's path to the single form every backend agrees on.

    A path reaches the library the way a caller wrote it — with backslashes,
    doubled slashes, ``.`` and ``..`` segments, leading and trailing slashes.
    A backend must never see that variety: two paths that name the same file
    have to arrive identical, and one that climbs above the root must be caught
    before a filesystem or an object store is asked about it. Every path crosses
    this boundary exactly once, so the backends downstream receive plain paths
    and never guard against these cases themselves.
    """

    def normalize_path(self, path: str) -> str:
        """Return ``path`` reduced to its plain, root-relative form.

        Args:
            path: The path as the caller gave it.

        Returns:
            The path with separators unified, redundant segments removed and no
            leading or trailing separator.
        """
        ...

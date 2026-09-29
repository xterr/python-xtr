"""Moving paths in and out of the root a backend actually stores under."""

from __future__ import annotations

from typing import final

__all__ = ["PathPrefixer"]


@final
class PathPrefixer:
    """Joins a caller's path to a backend's root and strips it back off again.

    A backend often stores everything under one root — a directory, a bucket
    key prefix — that the caller never sees. This prefixer owns that translation
    in one place: every path going down to the backend is prefixed, every path
    coming back up in a listing has the prefix removed, so the rest of the
    library works in caller-relative paths and the root lives here alone.

    The root is stored once, in a normalized shape, so joining is a plain string
    concatenation with no per-call trimming. A non-empty root always ends with
    the separator; an empty root stays empty so a prefixer with no root is a
    transparent pass-through; a root that is only the separator stays the
    separator, keeping a leading-slash convention intact.
    """

    __slots__ = ("_prefix", "_separator")

    def __init__(self, prefix: str, separator: str = "/") -> None:
        """Store the root in the shape every method below relies on.

        Args:
            prefix: The root every path is placed under. Trailing separators are
                folded so ``"a"`` and ``"a/"`` behave identically.
            separator: The character that joins segments in this backend.
        """
        stripped = prefix.rstrip("\\/")
        if stripped != "" or prefix == separator:
            self._prefix = stripped + separator
        else:
            self._prefix = ""
        self._separator = separator

    def prefix_path(self, path: str) -> str:
        """Place ``path`` under the root, dropping any leading separator it carries."""
        return self._prefix + path.lstrip("\\/")

    def strip_prefix(self, path: str) -> str:
        """Return ``path`` with the stored root removed from its front."""
        return path[len(self._prefix) :]

    def strip_directory_prefix(self, path: str) -> str:
        """Return a directory ``path`` with the root removed and no trailing separator."""
        return self.strip_prefix(path).rstrip("\\/")

    def prefix_directory_path(self, path: str) -> str:
        """Place a directory ``path`` under the root, ending it with the separator.

        An empty result — an empty root joined to an empty path — stays empty
        rather than becoming a lone separator, and a result that already ends
        with the separator is left as it is.
        """
        prefixed = self.prefix_path(path.rstrip("\\/"))
        if prefixed == "" or prefixed.endswith(self._separator):
            return prefixed
        return prefixed + self._separator

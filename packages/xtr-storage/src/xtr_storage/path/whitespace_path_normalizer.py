"""Resolving a path to its plainest form before a backend ever sees it."""

from __future__ import annotations

import unicodedata
from typing import final

from typing_extensions import override

from xtr_storage.exception import CorruptedPathDetectedError, PathTraversalDetectedError

from .path_normalizer_interface import PathNormalizerInterface

__all__ = ["WhitespacePathNormalizer"]


@final
class WhitespacePathNormalizer(PathNormalizerInterface):
    """Reduces a path to one canonical form and refuses the paths a backend can't trust.

    The name keeps the intent explicit: the normalizer folds away the
    "whitespace" of path writing — the backslashes, the doubled and edge
    separators, the ``.`` and ``..`` segments — so that two spellings of the
    same file collapse to one string. It resolves in memory, never touching a
    filesystem, which is why a ``..`` is settled by counting segments rather than
    by asking where a symlink points.

    Two paths are refused rather than resolved. One that carries a control or
    formatting character (anything Unicode files under category ``C``) cannot be
    a real name — such a character survives a comparison but not a filesystem, a
    url or a log line — so it raises rather than travelling on. One whose ``..``
    segments walk above the root would name a file the storage does not answer
    for, so it raises too; a storage may also forbid ``..`` outright, in which
    case any parent segment is refused whether or not there is something to pop.
    """

    __slots__ = ("_allow_relative_path_traversal",)

    def __init__(self, allow_relative_path_traversal: bool = True) -> None:
        """Record whether a resolvable ``..`` segment is allowed.

        Args:
            allow_relative_path_traversal: When true, a ``..`` pops the segment
                before it and only a ``..`` with nothing left to pop is refused.
                When false, any ``..`` is refused outright.
        """
        self._allow_relative_path_traversal = allow_relative_path_traversal

    @override
    def normalize_path(self, path: str) -> str:
        """Return ``path`` in canonical form, or raise if it cannot be trusted."""
        normalized = path.replace("\\", "/")
        for character in normalized:
            if unicodedata.category(character).startswith("C"):
                raise CorruptedPathDetectedError(path)

        segments: list[str] = []
        for segment in normalized.split("/"):
            if segment in {"", "."}:
                continue
            if segment == "..":
                if not self._allow_relative_path_traversal or not segments:
                    raise PathTraversalDetectedError(path)
                del segments[-1]
                continue
            segments.append(segment)

        return "/".join(segments)

"""A URL taken apart into the pieces a request is built from."""

from __future__ import annotations

from typing import NamedTuple, final

from typing_extensions import override

__all__ = ["UrlParts"]


@final
class UrlParts(NamedTuple):
    """The five pieces of a URL, each carrying its own punctuation.

    The delimiters belong to the piece that needs them — ``scheme`` keeps its
    colon, ``authority`` its leading slashes, ``query`` its question mark,
    ``fragment`` its hash — so writing the URL back out is joining whatever is
    there, and a piece nobody named is ``None`` rather than an empty string
    that cannot be told from one.

    That is what resolving a relative URL needs: "the path was given but the
    authority was not" is a different question from "the path is empty", and
    only ``None`` answers it.
    """

    scheme: str | None
    authority: str | None
    path: str | None
    query: str | None
    fragment: str | None

    @override
    def __str__(self) -> str:
        """Write the parts back out as the URL they came from."""
        return "".join(part for part in self if part is not None)

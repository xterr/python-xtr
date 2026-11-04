"""``multipart/alternative``: one content in several forms."""

from __future__ import annotations

from typing import final

from typing_extensions import override

from xtr_mime.part.abstract_multipart_part import AbstractMultipartPart

__all__ = ["AlternativePart"]


@final
class AlternativePart(AbstractMultipartPart):
    """The same content in several forms, the one a reader prefers last: text, then HTML."""

    __slots__ = ()

    @override
    def get_media_subtype(self) -> str:
        """Return ``alternative``."""
        return "alternative"

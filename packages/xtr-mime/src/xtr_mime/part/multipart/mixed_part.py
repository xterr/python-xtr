"""``multipart/mixed``: a body followed by attachments."""

from __future__ import annotations

from typing import final

from typing_extensions import override

from xtr_mime.part.abstract_multipart_part import AbstractMultipartPart

__all__ = ["MixedPart"]


@final
class MixedPart(AbstractMultipartPart):
    """Independent parts shown one after the other: the body first, then the attachments."""

    __slots__ = ()

    @override
    def get_media_subtype(self) -> str:
        """Return ``mixed``."""
        return "mixed"

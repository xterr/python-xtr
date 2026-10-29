"""``multipart/related``: a main part and the parts it refers to."""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_mime.part.abstract_multipart_part import AbstractMultipartPart

if TYPE_CHECKING:
    from xtr_mime.part.abstract_part import AbstractPart

__all__ = ["RelatedPart"]


@final
class RelatedPart(AbstractMultipartPart):
    """A main part — an HTML body — followed by the parts it shows, found by content id.

    Every part after the main one is given a Content-ID header if it has none, so the main
    part has something to refer to.
    """

    __slots__ = ()

    def __init__(self, main_part: AbstractPart, part: AbstractPart, *parts: AbstractPart) -> None:
        """Keep the main part first, then the others, giving each a content id it lacks."""
        for related in (part, *parts):
            if not related.get_headers().has("Content-ID"):
                related.get_headers().set_header_body(
                    "id", "Content-ID", f"{secrets.token_hex(16)}@xtr"
                )
        super().__init__(main_part, part, *parts)

    @override
    def get_media_subtype(self) -> str:
        """Return ``related``."""
        return "related"

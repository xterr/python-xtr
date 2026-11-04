"""``multipart/digest``: a collection of whole messages."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_mime.part.abstract_multipart_part import AbstractMultipartPart

if TYPE_CHECKING:
    from xtr_mime.part.message_part import MessagePart

__all__ = ["DigestPart"]


@final
class DigestPart(AbstractMultipartPart):
    """Messages gathered into one, as a mailing list digest is; every part is a message."""

    __slots__ = ()

    def __init__(self, *parts: MessagePart) -> None:
        """Keep the messages, in order."""
        super().__init__(*parts)

    @override
    def get_media_subtype(self) -> str:
        """Return ``digest``."""
        return "digest"

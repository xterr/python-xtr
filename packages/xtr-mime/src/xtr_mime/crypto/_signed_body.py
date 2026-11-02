"""The body of a signed message: the bytes that were signed, rendered again exactly as they were."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, ClassVar, final

from typing_extensions import override

from xtr_mime._engine import build_verbatim, set_fields
from xtr_mime.part import AbstractPart

if TYPE_CHECKING:
    from xtr_mime._engine import EnginePart
    from xtr_mime.header import Headers

__all__ = ["SignedBody"]

# The engine ends the headers it writes with the first empty line.
_END_OF_HEADERS = b"\r\n\r\n"


@final
class SignedBody(AbstractPart):
    """A body frozen at signing: the bytes the rendered message holds, not built again.

    A body is built anew at each rendering, and some do not come out the same: an attached
    message makes up a new Message-ID, a stream that cannot seek back is read once and is
    empty after; and the engine, reading those bytes back, would write some of the headers
    inside them otherwise. The signature covers the bytes signed, so the signed message keeps
    them and writes them as they are. The body's headers are the ones it was rendered with;
    the part takes no header added later.

    The part signed is kept as well, for what reads a body's fields rather than its bytes —
    :class:`~xtr_mime.MessageConverter`, turning the signed message back into an email.
    """

    __slots__: ClassVar[tuple[str, ...]] = (
        "_body",
        "_media_subtype",
        "_media_type",
        "_part",
        "_prepared",
    )

    def __init__(self, body: AbstractPart, rendered: bytes) -> None:
        """Freeze ``body`` as ``rendered`` — a whole message holding it — wrote it.

        Raises:
            RfcComplianceError: A header of ``body`` is refused.
        """
        super().__init__()
        self._part: AbstractPart = body
        self._media_type: str = body.get_media_type()
        self._media_subtype: str = body.get_media_subtype()
        self._prepared: Headers = body.get_prepared_headers()
        self._body: bytes = rendered.partition(_END_OF_HEADERS)[2]

    def get_signed_part(self) -> AbstractPart:
        """Return the part the frozen bytes were rendered from."""
        return self._part

    @override
    def get_media_type(self) -> str:
        return self._media_type

    @override
    def get_media_subtype(self) -> str:
        return self._media_subtype

    @override
    def get_prepared_headers(self) -> Headers:
        """Return a copy of the headers the body was rendered with."""
        return copy.copy(self._prepared)

    @override
    def _to_engine(self) -> EnginePart:
        part = build_verbatim(self._body)
        set_fields(part, self._prepared.to_array())
        return part

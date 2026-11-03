"""The body of a signed message: the bytes that were signed, rendered again exactly as they were."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, ClassVar, final

from typing_extensions import override

from xtr_mime._engine import build_verbatim, set_fields
from xtr_mime.part import AbstractPart

if TYPE_CHECKING:
    from typing import Self

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

    A signer builds it; :meth:`from_frozen` builds it again from what one holds — a queued
    message read back in another process — and it renders the same bytes there.
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
        self._freeze(body, body.get_prepared_headers(), rendered.partition(_END_OF_HEADERS)[2])

    @classmethod
    def from_frozen(cls, part: AbstractPart, headers: Headers, body: bytes) -> Self:
        """Build the body ``part`` froze as: written with ``headers``, then ``body`` as it is.

        ``headers`` are the prepared headers of a body frozen before, and ``body`` the bytes it
        writes after them — what :meth:`get_prepared_headers` and :meth:`body_to_iterable`
        give. ``part`` is not rendered: it is kept for what reads the body's fields.
        """
        frozen = cls.__new__(cls)
        AbstractPart.__init__(frozen)
        frozen._freeze(part, copy.copy(headers), body)  # noqa: SLF001 -- built by its own class.
        return frozen

    def _freeze(self, part: AbstractPart, prepared: Headers, body: bytes) -> None:
        self._part: AbstractPart = part
        self._media_type: str = part.get_media_type()
        self._media_subtype: str = part.get_media_subtype()
        self._prepared: Headers = prepared
        self._body: bytes = body

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

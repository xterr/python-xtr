"""The body of a signed message: the bytes that were signed, rendered again exactly as they were."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, ClassVar, final

from typing_extensions import override

from xtr_mime._engine import parse, set_fields
from xtr_mime.part import AbstractPart

if TYPE_CHECKING:
    from xtr_mime._engine import EnginePart
    from xtr_mime.header import Headers

__all__ = ["SignedBody"]


@final
class SignedBody(AbstractPart):
    """A body frozen at signing: read back from the rendered message, not built again.

    A body is built anew at each rendering, and some do not come out the same: an attached
    message makes up a new Message-ID, a stream that cannot seek back is read once and is
    empty after. The signature covers the bytes signed, so the signed message carries them,
    read back by the engine into its own tree, which it writes again byte for byte. The
    body's headers are the ones it was rendered with; the part takes no header added later.
    """

    __slots__: ClassVar[tuple[str, ...]] = (
        "_media_subtype",
        "_media_type",
        "_prepared",
        "_rendered",
    )

    def __init__(self, body: AbstractPart, rendered: bytes) -> None:
        """Freeze ``body`` as ``rendered`` — a whole message holding it — wrote it.

        Raises:
            RfcComplianceError: A header of ``body`` is refused.
        """
        super().__init__()
        self._media_type: str = body.get_media_type()
        self._media_subtype: str = body.get_media_subtype()
        self._prepared: Headers = body.get_prepared_headers()
        self._rendered: bytes = rendered

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
        # Read back at each rendering: the engine's tree is changed by what renders it.
        tree = parse(self._rendered)
        # The message's own headers are read back too; the part keeps only its own.
        set_fields(tree, self._prepared.to_array())
        return tree

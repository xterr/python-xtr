"""A part whose body is already encoded: what an S/MIME signer or encrypter writes."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, final

from typing_extensions import override

from xtr_mime._engine import parse

from .abstract_part import AbstractPart

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_mime._engine import EnginePart
    from xtr_mime.header import Headers

__all__ = ["SMimePart"]


@final
class SMimePart(AbstractPart):
    """A body written as it is given, under a media type and Content-Type parameters.

    A signature covers bytes: the body of a ``multipart/signed`` part, its boundaries and the
    signed part inside, must reach the receiver exactly as they were signed. The body is read
    back by the engine under the part's headers and written again byte for byte, its lines
    ending in CRLF.
    """

    __slots__: ClassVar[tuple[str, ...]] = (
        "_body",
        "_media_subtype",
        "_media_type",
        "_parameters",
    )

    def __init__(
        self,
        body: str | bytes,
        media_type: str,
        media_subtype: str,
        parameters: Mapping[str, str],
    ) -> None:
        """Keep the body, already encoded, and the Content-Type it is written under.

        Args:
            body: The body as it is sent, after the blank line ending the headers.
            media_type: The part of Content-Type before the slash.
            media_subtype: The part of Content-Type after the slash.
            parameters: The Content-Type parameters, ``boundary`` for a multipart.
        """
        super().__init__()
        self._body: bytes = (
            body.encode("utf-8", "surrogateescape") if isinstance(body, str) else body
        )
        self._media_type: str = media_type
        self._media_subtype: str = media_subtype
        self._parameters: dict[str, str] = dict(parameters)

    @override
    def get_media_type(self) -> str:
        return self._media_type

    @override
    def get_media_subtype(self) -> str:
        return self._media_subtype

    @override
    def get_prepared_headers(self) -> Headers:
        """Return a copy of the headers with Content-Type and its parameters set on it."""
        headers = super().get_prepared_headers()
        for name, value in self._parameters.items():
            headers.set_header_parameter("Content-Type", name, value)
        return headers

    @override
    def _to_engine(self) -> EnginePart:
        # The body is read back under the headers it is written with: a multipart's parts are
        # found by the boundary its Content-Type names.
        head = self.get_prepared_headers().to_string()
        return parse(head.encode("utf-8", "surrogateescape") + b"\r\n" + self._body)

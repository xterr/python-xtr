"""What every MIME part shares: headers of its own, prepared headers, and its rendering."""

from __future__ import annotations

import copy
from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, ClassVar

from xtr_mime._engine import render, to_bytes, to_string
from xtr_mime.header import Headers

if TYPE_CHECKING:
    from collections.abc import Iterator
    from typing import Self

    from xtr_mime._engine import EnginePart

__all__ = ["AbstractPart"]

# Headers never hold an empty line, so the first one ends them.
_END_OF_HEADERS = b"\r\n\r\n"


class AbstractPart(metaclass=ABCMeta):
    """A MIME part: headers, a blank line, a body.

    :meth:`get_headers` holds what the caller adds; :meth:`get_prepared_headers` adds what the
    part itself decides — its media type above all — to a copy, so rendering never changes
    the part. A subclass says what its media type is and how the engine builds it.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_headers",)

    def __init__(self) -> None:
        """Start with no headers of the caller's."""
        self._headers: Headers = Headers()

    def get_headers(self) -> Headers:
        """Return the part's own headers, which the caller may add to."""
        return self._headers

    def set_content_type_parameter(self, name: str, value: str) -> Self:
        """Set a parameter of Content-Type, such as ``method`` for ``text/calendar``.

        Raises:
            RfcComplianceError: ``name`` is not a token or is longer than 40 characters.
        """
        if not self._headers.has("Content-Type"):
            _ = self._headers.add_parameterized_header(
                "Content-Type", f"{self.get_media_type()}/{self.get_media_subtype()}"
            )
        self._headers.set_header_parameter("Content-Type", name, value)
        return self

    def get_prepared_headers(self) -> Headers:
        """Return a copy of the headers with what the part decides set on it.

        Changing the copy leaves the part as it is.
        """
        headers = copy.copy(self._headers)
        headers.set_header_body(
            "parameterized", "Content-Type", f"{self.get_media_type()}/{self.get_media_subtype()}"
        )
        return headers

    def to_string(self) -> str:
        """Render the part: its prepared headers, a blank line, its encoded body.

        Bytes that are not UTF-8 (an 8bit body) survive as surrogates, as
        :meth:`to_iterable` writes them.

        Raises:
            InvalidArgumentError: The body cannot be read or written as asked.
            RfcComplianceError: A header is refused.
        """
        return to_string(self._to_engine())

    def to_iterable(self) -> Iterator[bytes]:
        """Render the part in the pieces the engine writes, as a mail server receives them.

        Raises:
            InvalidArgumentError: As :meth:`to_string` does.
            RfcComplianceError: As :meth:`to_string` does.
        """
        yield from render(self._to_engine())

    def body_to_string(self) -> str:
        """Render the encoded body alone, as :meth:`to_string` writes it."""
        return self._render_body().decode("utf-8", "surrogateescape")

    def body_to_iterable(self) -> Iterator[bytes]:
        """Render the encoded body alone, as :meth:`to_iterable` writes it."""
        yield self._render_body()

    def as_debug_string(self) -> str:
        """Describe the part in one line: its media type."""
        return f"{self.get_media_type()}/{self.get_media_subtype()}"

    @abstractmethod
    def get_media_type(self) -> str:
        """Return the media type, the part of Content-Type before the slash."""

    @abstractmethod
    def get_media_subtype(self) -> str:
        """Return the media subtype, the part of Content-Type after the slash."""

    @abstractmethod
    def _to_engine(self) -> EnginePart:
        """Build the part as the engine renders it, headers set from the prepared ones."""

    def _render_body(self) -> bytes:
        return to_bytes(self._to_engine()).partition(_END_OF_HEADERS)[2]

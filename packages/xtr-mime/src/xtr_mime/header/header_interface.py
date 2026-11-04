"""What every header of a message is."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["HeaderInterface"]


@runtime_checkable
class HeaderInterface(Protocol):
    """One header field: a name, a typed body, and the text it is written as.

    The body's type depends on the header — text, an address, a list of addresses, a date,
    identifiers — so :meth:`get_body` and :meth:`set_body` deal in ``object``, and each class
    checks what it is given. The typed accessors of each class are the ones to call when the
    class is known.
    """

    def set_body(self, body: object) -> None:
        """Replace the body; the type depends on the header.

        Raises:
            InvalidArgumentError: ``body`` is not of the type this header holds.
        """
        ...

    def get_body(self) -> object:
        """Return the body; the type depends on the header."""
        ...

    def set_charset(self, charset: str) -> None:
        """Set the charset the body is meant to be encoded in."""
        ...

    def get_charset(self) -> str:
        """Return the charset, ``utf-8`` unless set."""
        ...

    def set_language(self, language: str) -> None:
        """Set the language of the body, an RFC 5646 tag such as ``en-us``."""
        ...

    def get_language(self) -> str | None:
        """Return the language, ``None`` unless set."""
        ...

    def get_name(self) -> str:
        """Return the name, as given."""
        ...

    def set_max_line_length(self, line_length: int) -> None:
        """Set the line length the header is meant to be folded at."""
        ...

    def get_max_line_length(self) -> int:
        """Return the line length, 76 unless set."""
        ...

    def to_string(self) -> str:
        """Return the whole field as written in a message, folded, without the final CRLF."""
        ...

    def get_body_as_string(self) -> str:
        """Return the body as written in a message, encoded but on one line."""
        ...

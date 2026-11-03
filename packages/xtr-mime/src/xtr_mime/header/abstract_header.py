"""What every header class shares: a checked name and rendering through the engine."""

from __future__ import annotations

import re
from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, ClassVar, Final, NoReturn

from xtr_mime._engine import fold_header, header_body, header_field
from xtr_mime._error_text import capped
from xtr_mime.exception import InvalidArgumentError, RfcComplianceError

if TYPE_CHECKING:
    from xtr_mime._engine import HeaderValue

__all__ = ["AbstractHeader"]

# RFC 5322, 2.2: printable ASCII. A colon is kept for a transport reading prefixed names
# (``h:Sender``, ``o:tag``) as form fields; such a header is never written as a field.
_NAME: Final = re.compile(r"[!-~]+")


class AbstractHeader(metaclass=ABCMeta):
    """A header with a checked name, rendered by the engine from the value it holds.

    A subclass says what its body is and which engine value writes it; encoding and folding
    are the engine's. The charset, language and line length are kept for the code that reads
    them, but the engine writes every encoded word and parameter in UTF-8, without a language,
    folded at 76 columns.

    A name may hold a colon (``h:Sender``): such a header exists only for a transport that
    reads it as a form field, through :meth:`get_body_as_string`. A reader ends a name at its
    first colon — ``Bcc:victim@example.com,x`` would be read as a Bcc header — so
    :meth:`to_string` refuses it, and no message carries it.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_charset", "_language", "_line_length", "_name")

    def __init__(self, name: str) -> None:
        """Keep ``name`` once checked.

        It is checked here, not when the header is written: a header with a line break in
        its name would start a header of its own.

        Raises:
            RfcComplianceError: ``name`` is not printable ASCII, or holds a space.
        """
        if not _NAME.fullmatch(name):
            raise RfcComplianceError(
                f'The header name "{capped(name)}" contains characters that are not allowed in a '
                "header name."
            )
        self._name: str = name
        self._charset: str = "utf-8"
        self._language: str | None = None
        self._line_length: int = 76

    @abstractmethod
    def get_body(self) -> object:
        """Return the body; each class says what type it is."""

    @abstractmethod
    def set_body(self, body: object) -> None:
        """Replace the body, once checked to be of the type this header holds.

        Raises:
            InvalidArgumentError: ``body`` is not of that type.
        """

    @abstractmethod
    def _engine_value(self) -> HeaderValue:
        """Return the value the engine writes this header from."""

    def set_charset(self, charset: str) -> None:
        """Set the charset the body is meant to be encoded in."""
        self._charset = charset

    def get_charset(self) -> str:
        """Return the charset, ``utf-8`` unless set."""
        return self._charset

    def set_language(self, language: str) -> None:
        """Set the language of the body, an RFC 5646 tag such as ``en-us``."""
        self._language = language

    def get_language(self) -> str | None:
        """Return the language, ``None`` unless set."""
        return self._language

    def get_name(self) -> str:
        """Return the name, as given."""
        return self._name

    def set_max_line_length(self, line_length: int) -> None:
        """Set the line length the header is meant to be folded at."""
        self._line_length = line_length

    def get_max_line_length(self) -> int:
        """Return the line length, 76 unless set."""
        return self._line_length

    def to_string(self) -> str:
        """Return the whole field as the engine writes it, folded, without the final CRLF.

        Raises:
            RfcComplianceError: The name holds a colon, or the engine refuses the value: a
                control character, an address that would not read back, a parameter or
                identifier the grammar refuses.
        """
        return fold_header(self._name, self._engine_value())

    def get_body_as_string(self) -> str:
        """Return the body as the engine writes it, joined back onto one line, whatever the name.

        Raises:
            RfcComplianceError: The engine refuses the value, as :meth:`to_string` says.
        """
        return header_body(self._name, self._engine_value()).replace("\r\n", "")

    def to_field(self) -> str | None:
        """Return the field as :meth:`to_string` writes it, ``None`` when it has no body.

        What :class:`Headers` renders a header with: the value is folded once for both, where
        asking :meth:`get_body_as_string` then :meth:`to_string` folds it twice. A subclass
        that writes itself its own way is rendered through those two methods instead.

        Raises:
            RfcComplianceError: As :meth:`to_string` does, for a header with a body.
        """
        kind = type(self)
        if (
            kind.to_string is not AbstractHeader.to_string
            or kind.get_body_as_string is not AbstractHeader.get_body_as_string
        ):
            return self.to_string() if self.get_body_as_string() else None
        return header_field(self._name, self._engine_value())

    def _refuse_body(self, expected: str, body: object) -> NoReturn:
        raise InvalidArgumentError(
            f'The "{self._name}" header takes {expected} (got "{type(body).__name__}").'
        )

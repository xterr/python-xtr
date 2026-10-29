"""What every header class shares: a checked name and rendering through the engine."""

from __future__ import annotations

import re
from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, ClassVar, Final, NoReturn

from xtr_mime._engine import fold_header, header_body
from xtr_mime.exception import InvalidArgumentError, RfcComplianceError

if TYPE_CHECKING:
    from xtr_mime._engine import HeaderValue

__all__ = ["AbstractHeader"]

# RFC 5322, 2.2: printable ASCII. A colon is kept: an API reading prefixed names
# (``h:Sender``, ``o:tag``) gets them as given, and a reader ends the name at the first one.
_NAME: Final = re.compile(r"[!-~]+")


class AbstractHeader(metaclass=ABCMeta):
    """A header with a checked name, rendered by the engine from the value it holds.

    A subclass says what its body is and which engine value writes it; encoding and folding
    are the engine's. The charset, language and line length are kept for the code that reads
    them, but the engine writes every encoded word and parameter in UTF-8, without a language,
    folded at 76 columns.
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
                f'The header name "{name}" contains characters that are not allowed in a '
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
            RfcComplianceError: The engine refuses the value: a control character, an address
                that would not read back, a parameter or identifier the grammar refuses.
        """
        return fold_header(self._name, self._engine_value())

    def get_body_as_string(self) -> str:
        """Return the body as the engine writes it, joined back onto one line.

        Raises:
            RfcComplianceError: As :meth:`to_string` does.
        """
        return header_body(self._name, self._engine_value()).replace("\r\n", "")

    def _refuse_body(self, expected: str, body: object) -> NoReturn:
        raise InvalidArgumentError(
            f'The "{self._name}" header takes {expected} (got "{type(body).__name__}").'
        )

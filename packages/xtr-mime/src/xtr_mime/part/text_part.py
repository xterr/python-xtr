"""A text part, and the base of every part whose body is a single piece of content."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO, ClassVar, Final, Literal, TypeAlias

from typing_extensions import override

from xtr_mime._engine import BinaryLeaf, TextLeaf, build_binary, build_text, set_fields
from xtr_mime._error_text import body_charset_error, check_charset, escaped
from xtr_mime.exception import InvalidArgumentError

from .abstract_part import AbstractPart
from .file import File

if TYPE_CHECKING:
    from typing import Self

    from xtr_mime._engine import EnginePart
    from xtr_mime.header import Headers

__all__ = ["TextPart"]

_Encoding: TypeAlias = Literal["quoted-printable", "base64", "8bit", "binary"]
_ENCODINGS: Final[tuple[_Encoding, ...]] = ("quoted-printable", "base64", "8bit", "binary")


class TextPart(AbstractPart):
    """A part holding one body: text in a charset, or bytes when the charset is ``None``.

    The body is a string, bytes, a binary file or a :class:`File`; a file is read each time
    the part is rendered, a seekable one from its start. Without an explicit transfer
    encoding, one is chosen when rendering: ``8bit`` for a form field, ``base64`` for bytes
    with no charset, ``quoted-printable`` for text. In a mail, ``8bit`` and ``binary`` bodies
    have their line breaks written as CRLF, the only line end SMTP carries.
    """

    __slots__: ClassVar[tuple[str, ...]] = (
        "_body",
        "_charset",
        "_disposition",
        "_encoding",
        "_name",
        "_subtype",
    )

    def __init__(
        self,
        body: str | bytes | BinaryIO | File,
        charset: str | None = "utf-8",
        subtype: str = "plain",
        encoding: str | None = None,
    ) -> None:
        """Keep the body, its charset and subtype, and the transfer encoding asked for.

        Raises:
            TypeError: ``body`` is none of the types a body may be.
            InvalidArgumentError: ``body`` is a :class:`File` naming a directory or a file
                this process may not read, or ``encoding`` is not one the part knows.
        """
        super().__init__()
        if not isinstance(body, str | bytes | File) and not hasattr(body, "read"):
            raise TypeError(
                f'The body of "xtr_mime.part.{type(self).__name__}" must be a string, bytes, a '
                f'binary file or an instance of "xtr_mime.part.File" (got '
                f'"{type(body).__name__}").'
            )
        if isinstance(body, File):
            _check_readable(body.get_path())
        self._body: str | bytes | BinaryIO | File = body
        self._charset: str | None = charset
        self._subtype: str = subtype
        self._encoding: _Encoding | None = _parse_encoding(encoding)
        self._disposition: str | None = None
        self._name: str | None = None

    @override
    def get_media_type(self) -> str:
        """Return ``text``."""
        return "text"

    @override
    def get_media_subtype(self) -> str:
        """Return the subtype given, ``plain`` by default."""
        return self._subtype

    def set_disposition(self, disposition: str) -> Self:
        """Set how the part is shown: ``attachment``, ``inline`` or ``form-data``."""
        self._disposition = disposition
        return self

    def get_disposition(self) -> str | None:
        """Return the disposition, ``None`` unless set."""
        return self._disposition

    def set_name(self, name: str) -> Self:
        """Set the name of the part: a file's name, or a form field's."""
        self._name = name
        return self

    def get_name(self) -> str | None:
        """Return the name, ``None`` unless set."""
        return self._name

    def get_body(self) -> str | bytes:
        """Return the body before transfer encoding: a string as given, bytes otherwise.

        Raises:
            InvalidArgumentError: The body is a :class:`File` that cannot be read.
        """
        body = self._body
        match body:
            case str() | bytes():
                return body
            case File():
                return _read(body.get_path())
            case _:
                if body.seekable():
                    _ = body.seek(0)
                return body.read()

    @override
    def get_prepared_headers(self) -> Headers:
        """Return the headers with Content-Type, its charset and name, and the encoding set.

        A form field carries its name in Content-Disposition only.
        """
        headers = super().get_prepared_headers()
        if self._charset:
            headers.set_header_parameter("Content-Type", "charset", self._charset)
        if self._name and self._disposition != "form-data":
            headers.set_header_parameter("Content-Type", "name", self._name)
        headers.set_header_body("text", "Content-Transfer-Encoding", self._get_encoding())
        if not headers.has("Content-Disposition") and self._disposition is not None:
            headers.set_header_body("parameterized", "Content-Disposition", self._disposition)
            if self._name:
                headers.set_header_parameter("Content-Disposition", "name", self._name)
        return headers

    @override
    def as_debug_string(self) -> str:
        """Describe the part: its media type, charset and disposition."""
        description = super().as_debug_string()
        if self._charset is not None:
            description += f" charset: {self._charset}"
        if self._disposition is not None:
            description += f" disposition: {self._disposition}"
        return description

    @override
    def _to_engine(self) -> EnginePart:
        encoding = self._get_encoding()
        content = self.get_body()
        charset = self._charset
        if charset is not None and (encoding != "binary" or isinstance(content, str)):
            check_charset(charset)
        try:
            if charset is not None and encoding != "binary":
                text = content if isinstance(content, str) else content.decode(charset)
                leaf = TextLeaf(
                    content=text,
                    subtype=self.get_media_subtype(),
                    charset=charset,
                    transfer_encoding=encoding,
                )
                part = build_text(leaf)
            else:
                data = content.encode(charset or "utf-8") if isinstance(content, str) else content
                binary = BinaryLeaf(
                    content=data,
                    maintype=self.get_media_type(),
                    subtype=self.get_media_subtype(),
                    transfer_encoding=encoding,
                )
                part = build_binary(binary)
        except (LookupError, UnicodeError) as error:
            raise body_charset_error(charset or "utf-8", error) from error
        set_fields(part, self.get_prepared_headers().to_array())
        return part

    def _get_encoding(self) -> _Encoding:
        if self._encoding is not None:
            return self._encoding
        if self._disposition == "form-data":
            return "8bit"
        if self._charset is None:
            return "base64"
        return "quoted-printable"


def _parse_encoding(encoding: str | None) -> _Encoding | None:
    if encoding is None:
        return None
    for known in _ENCODINGS:
        if encoding == known:
            return known
    names = '", "'.join(_ENCODINGS)
    raise InvalidArgumentError(f'The encoding must be one of "{names}" ("{encoding}" given).')


def _check_readable(path: str) -> None:
    # os.path answers False for a path it cannot even stat, where Path raises a
    # PermissionError before 3.14.
    if os.path.isdir(path) or (os.path.isfile(path) and not os.access(path, os.R_OK)):  # noqa: PTH112, PTH113 — see above.
        raise InvalidArgumentError(f'Path "{escaped(path)}" is not readable.')


def _read(path: str) -> bytes:
    try:
        return Path(path).read_bytes()
    except OSError as error:
        raise InvalidArgumentError(
            f'Unable to open path "{escaped(path)}": Failed to open stream: {error.strerror}.'
        ) from error
    except ValueError as error:
        raise InvalidArgumentError(
            f'Unable to open path "{escaped(path)}": Failed to open stream: {error}.'
        ) from error

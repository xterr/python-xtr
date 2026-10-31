"""``multipart/form-data`` (RFC 7578): the body of an HTTP form upload."""

from __future__ import annotations

import base64
import binascii
import copy
import re
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Final, TypeAlias, cast, final

from typing_extensions import override

from xtr_mime._engine import parse
from xtr_mime.exception import InvalidArgumentError, RfcComplianceError
from xtr_mime.header import ParameterizedHeader
from xtr_mime.part.abstract_multipart_part import AbstractMultipartPart
from xtr_mime.part.text_part import TextPart

if TYPE_CHECKING:
    from collections.abc import Iterator

    from xtr_mime._engine import EnginePart
    from xtr_mime.header import HeaderInterface

__all__ = ["FormDataPart", "FormFields", "FormValue"]

FormValue: TypeAlias = "str | TextPart | Mapping[str | int, FormValue] | Sequence[FormValue]"
"""A field's value: text, a part, or fields nested under the field's name."""

FormFields: TypeAlias = "Mapping[str | int, FormValue] | Sequence[FormValue]"
"""A form's fields; at the top, an integer key holds a one-field mapping, so names repeat."""

# RFC 2045, 5.1: a parameter value written without quotes.
_TOKEN: Final = re.compile(r"[!#$%&'*+\-.^_`{|}~0-9A-Za-z]+")
# WHATWG HTML, form submission: a field name or filename has these three replaced, nothing else.
_WHATWG_ESCAPES: Final = str.maketrans({'"': "%22", "\r": "%0D", "\n": "%0A"})
_QUOTED_ESCAPES: Final = str.maketrans({"\\": "\\\\", '"': '\\"'})
# What would end a header line early, or be read as its end.
_LINE_BREAKERS: Final = frozenset("\r\n\x00")


@final
class FormDataPart(AbstractMultipartPart):
    """A form: each field a part named in its Content-Disposition, as a browser sends it.

    A string becomes a UTF-8 text field; a :class:`TextPart` or :class:`DataPart` is copied
    and named after its field, the given part left as it is; nested fields are named
    ``name[key]``. A field without an explicit transfer encoding is written in ``8bit``, its
    bytes as they are — RFC 7578, 4.7 deprecates the header; an explicit one is kept for the
    receivers that ask for it.

    This is HTTP, not mail: the form writes its fields itself. A field name or filename is
    raw UTF-8 with ``"``, CR and LF escaped as browsers do, never in RFC 2231 form, and no
    header is folded. :meth:`get_prepared_headers` and :meth:`body_to_iterable` are the HTTP
    request's Content-Type and body.
    """

    __slots__ = ("_fields",)

    def __init__(self, fields: FormFields = ()) -> None:
        """Read the fields and their names.

        Raises:
            InvalidArgumentError: A value is not a string, a part or nested fields, or a
                top-level integer key holds other than a single field.
        """
        super().__init__()
        self._fields: list[tuple[str, str | TextPart]] = []
        for key, item in _entries(fields):
            _collect(self._fields, item, key, None)

    @override
    def get_media_subtype(self) -> str:
        """Return ``form-data``."""
        return "form-data"

    @override
    def get_parts(self) -> list[TextPart]:
        """Return a part per field, named after it, with the ``form-data`` disposition."""
        return [_field_part(name, value) for name, value in self._fields]

    @override
    def to_string(self) -> str:
        """Render the Content-Type header, a blank line and the body.

        Raises:
            InvalidArgumentError: A field's body cannot be read or written as asked.
            RfcComplianceError: A header would hold a line break, a NUL or a lone surrogate.
        """
        return b"".join(self.to_iterable()).decode("utf-8", "surrogateescape")

    @override
    def to_iterable(self) -> Iterator[bytes]:
        """Render the Content-Type header, a blank line and the body, in pieces.

        Raises:
            InvalidArgumentError: As :meth:`to_string` does.
            RfcComplianceError: As :meth:`to_string` does.
        """
        yield f"{self.get_prepared_headers().to_string()}\r\n".encode()
        yield from self.body_to_iterable()

    @override
    def body_to_string(self) -> str:
        """Render the body; bytes that are not UTF-8 survive as surrogates."""
        return b"".join(self.body_to_iterable()).decode("utf-8", "surrogateescape")

    @override
    def body_to_iterable(self) -> Iterator[bytes]:
        """Render the body, field by field: what an HTTP client sends.

        Raises:
            InvalidArgumentError: A field's body cannot be read or written as asked.
            RfcComplianceError: A header would hold a line break, a NUL or a lone surrogate.
        """
        boundary = self._get_boundary()
        for part in self.get_parts():
            yield f"--{boundary}\r\n".encode()
            yield from _render_field(part)
            yield b"\r\n"
        yield f"--{boundary}--\r\n".encode()

    @override
    def _to_engine(self) -> EnginePart:
        # Inside a mail the form is carried as written, which the engine reads back.
        return parse(b"".join(self.to_iterable()))


def _entries(fields: object) -> list[tuple[object, object]]:
    if isinstance(fields, Mapping):
        return list(cast("Mapping[object, object]", fields).items())
    return list(enumerate(cast("Sequence[object]", fields)))


def _is_nested(item: object) -> bool:
    return isinstance(item, Mapping) or (
        isinstance(item, Sequence) and not isinstance(item, str | bytes | bytearray)
    )


def _collect(
    fields: list[tuple[str, str | TextPart]], item: object, key: object, root: str | None
) -> None:
    """Add the field ``item`` under ``key``, or each field it nests, to ``fields``."""
    if root is None and isinstance(key, int) and _is_nested(item):
        entries = _entries(item)
        if len(entries) != 1:
            raise InvalidArgumentError(
                "Form field values with integer keys can only have one array element, the key "
                "being the field name and the value being the field value, "
                f"{len(entries)} provided."
            )
        [(key, item)] = entries
    name = str(key) if root is None else f"{root}[{key}]"
    if _is_nested(item):
        for child_key, child in _entries(item):
            _collect(fields, child, child_key, name)
        return
    if not isinstance(item, str | TextPart):
        raise InvalidArgumentError(
            f'The value of the form field "{name}" can only be a string, a sequence, a mapping, '
            f'or an instance of TextPart, "{type(item).__name__}" given.'
        )
    fields.append((name, item))


def _field_part(name: str, value: str | TextPart) -> TextPart:
    part = TextPart(value, "utf-8", "plain", "8bit") if isinstance(value, str) else copy.copy(value)
    return part.set_disposition("form-data").set_name(name)


def _render_field(part: TextPart) -> Iterator[bytes]:
    headers = part.get_prepared_headers()
    for header in headers.all():
        line = _header_line(header)
        if line is None:
            continue
        try:
            written = f"{line}\r\n".encode()
        except UnicodeError as error:
            raise RfcComplianceError(
                f"The {header.get_name()} header cannot be written in UTF-8: {error}."
            ) from error
        yield written
    yield b"\r\n"
    charset = headers.get_header_parameter("Content-Type", "charset") or None
    content = part.get_body()
    try:
        if isinstance(content, str):
            content = content.encode(charset or "utf-8", "surrogateescape")
    except (LookupError, UnicodeError) as error:
        raise InvalidArgumentError(
            f'The body is not "{charset or "utf-8"}" text: {error}.'
        ) from error
    encoding = headers.get_header_body("Content-Transfer-Encoding")
    yield _encode(content, encoding, text=charset is not None)


def _header_line(header: HeaderInterface) -> str | None:
    """Write one header on one line; ``None`` for a header with nothing to write."""
    if isinstance(header, ParameterizedHeader):
        is_form_data = (
            header.get_name().lower() == "content-disposition" and header.get_value() == "form-data"
        )
        parameters = [
            f"; {key}={_parameter(value, escape=is_form_data and key in {'name', 'filename'})}"
            for key, value in header.get_parameters().items()
            if value is not None
        ]
        line = f"{header.get_name()}: {header.get_value()}{''.join(parameters)}"
    else:
        body = header.get_body_as_string()
        if not body:
            return None
        line = f"{header.get_name()}: {body}"
    if _LINE_BREAKERS.intersection(line):
        raise RfcComplianceError(
            f"A form-data header must not contain a line break or a NUL: {line!r}."
        )
    return line


def _parameter(value: str, *, escape: bool) -> str:
    if escape:
        return f'"{value.translate(_WHATWG_ESCAPES)}"'
    if _TOKEN.fullmatch(value):
        return value
    return f'"{value.translate(_QUOTED_ESCAPES)}"'


def _encode(data: bytes, encoding: object, *, text: bool) -> bytes:
    """Write a field's body in its transfer encoding; 8bit and binary are the bytes as they are."""
    match encoding:
        case "base64":
            return b"\r\n".join(base64.encodebytes(data).splitlines())
        case "quoted-printable" if text:
            lines = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            return binascii.b2a_qp(lines, istext=True).replace(b"\n", b"\r\n")
        case "quoted-printable":
            return binascii.b2a_qp(data, istext=False).replace(b"\n", b"\r\n")
        case _:
            return data

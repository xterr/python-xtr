"""What a caller gave as a body, turned into something that can be sent."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterable, Iterable, Mapping
from typing import TYPE_CHECKING, Final, cast

from xtr_http_client.exception import InvalidArgumentError
from xtr_http_client.internal.debug_type import debug_type
from xtr_http_client.internal.query import build_query

if TYPE_CHECKING:
    from collections.abc import MutableMapping

    from xtr_http_client_contracts import QueryValue

__all__ = ["FORM_CONTENT_TYPE", "json_encode", "normalize_body"]

FORM_CONTENT_TYPE: Final = "application/x-www-form-urlencoded"
_ALREADY_A_FORM: Final = (FORM_CONTENT_TYPE, "multipart/form-data")
_ESCAPED_IN_DOCUMENTS: Final = {"<": r"\u003C", ">": r"\u003E", "&": r"\u0026", "'": r"\u0027"}
_ESCAPED_QUOTE: Final = re.compile(r'(?<!\\)((?:\\\\)*)\\"')


def normalize_body(
    body: object,
    normalized_headers: MutableMapping[str, list[str]] | None = None,
) -> bytes | Iterable[bytes] | AsyncIterable[bytes]:
    """Turn a body into bytes, or leave it as the stream of bytes it is.

    Bytes and text go as they are. A mapping is a form, written out as one and
    announced as one, because a server cannot guess that is what the bytes
    are. Anything that produces bytes — a list of chunks, an async iterator
    over a file — is left alone: it is sent as it is produced, which is the
    whole point of giving one.

    Args:
        body: What the caller wants sent: bytes, a string, a mapping of form
            fields, or anything that produces bytes.
        normalized_headers: The headers of the request, where a form announces
            itself. A content type the caller already chose is left alone, so
            a charset or a multipart boundary survives.

    Raises:
        InvalidArgumentError: When the body is of a shape nothing can be made
            of.
    """
    if isinstance(body, Mapping):
        # A form body is typed as a mapping of anything, because that is what a
        # caller writes; what can be written out is narrower, and `build_query`
        # is what refuses the rest by name.
        return _form(cast("Mapping[str, QueryValue]", body), normalized_headers)
    if isinstance(body, bytes):
        return body
    if isinstance(body, str):
        return body.encode()
    if isinstance(body, Iterable | AsyncIterable):
        # Nothing here reads it — it is sent as it is produced — so that it
        # yields bytes is a promise the caller keeps, and the only way to
        # check it would be to consume the body nobody has sent yet.
        return cast("Iterable[bytes] | AsyncIterable[bytes]", body)

    raise InvalidArgumentError(
        f'Option "body" must be bytes, a string, a mapping or an iterable of bytes, '
        f'"{debug_type(body)}" given.'
    )


def json_encode(value: object) -> bytes:
    """Encode a value as the JSON body of a request.

    Compact, so nothing is sent that is not data. ASCII, so no step between
    here and the server has to agree about an encoding. And the four
    characters that let a JSON document end up meaning something else where it
    is embedded — in HTML, in a script, in a quoted attribute — are escaped,
    so the document is safe to put anywhere while still decoding to the same
    value.

    Raises:
        InvalidArgumentError: When the value cannot be JSON: a set, an object
            of some other class, a circular structure, or a float that is not
            a number.
    """
    try:
        document = json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError) as error:
        raise InvalidArgumentError(f'Invalid value for "json" option: {error}') from error

    for character, escape in _ESCAPED_IN_DOCUMENTS.items():
        document = document.replace(character, escape)

    # Only a quote that closes a string may be left as it is; the lookbehind
    # counts the backslashes before it so an escaped backslash is not read as
    # escaping the quote that follows it.
    return _ESCAPED_QUOTE.sub(r"\1\\u0022", document).encode()


def _form(
    fields: Mapping[str, QueryValue],
    normalized_headers: MutableMapping[str, list[str]] | None,
) -> bytes:
    written = build_query(fields, option="body", form=True)
    if written == "":
        return b""

    if normalized_headers is not None and not _announced(normalized_headers):
        normalized_headers["content-type"] = [f"Content-Type: {FORM_CONTENT_TYPE}"]

    return written.encode()


def _announced(normalized_headers: Mapping[str, list[str]]) -> bool:
    lines = normalized_headers.get("content-type")
    content_type = lines[0] if lines else ""
    return any(form in content_type for form in _ALREADY_A_FORM)

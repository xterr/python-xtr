"""Parts built from xtr-mime's typed leaves, multiparts around them, and whole messages."""

from __future__ import annotations

import copy
from email.message import EmailMessage
from typing import TYPE_CHECKING, Final, cast

from xtr_mime.exception import InvalidArgumentError, RfcComplianceError

from ._fold import add_header, make_header
from ._grammar import SOURCE_FOLD, check_boundary, check_folded, check_name, check_token
from ._policy import POLICY, FoldedHeader
from ._render import VerbatimPart
from ._values import MessageIds, Parameterized

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ._policy import EnginePart
    from ._values import BinaryLeaf, HeaderValue, TextLeaf

__all__ = [
    "build_binary",
    "build_message",
    "build_multipart",
    "build_text",
    "build_verbatim",
    "prepend_fields",
    "set_fields",
]

# The transfer encodings whose body is the bytes themselves, nothing to decode.
_UNENCODED: Final = frozenset({"", "7bit", "8bit", "binary"})


def build_text(leaf: TextLeaf) -> EnginePart:
    """Build a text part; its body always ends with a line break, the engine adds one.

    Raises:
        InvalidArgumentError: Python knows no such charset, or the content cannot be written
            in it or in the transfer encoding.
        RfcComplianceError: The subtype or the charset is not a token, or a header value is
            refused.
    """
    check_token("media subtype", leaf.subtype)
    check_token("charset", leaf.charset)
    part: EnginePart = EmailMessage(policy=POLICY)
    try:
        part.set_content(
            leaf.content,
            subtype=leaf.subtype,
            charset=leaf.charset,
            cte=leaf.transfer_encoding,
        )
    except LookupError as error:
        raise InvalidArgumentError(f'The charset "{leaf.charset}" is unknown.') from error
    except UnicodeError as error:
        raise InvalidArgumentError(
            f'The text cannot be written as "{leaf.charset}" in "{leaf.transfer_encoding}": '
            f"{error}."
        ) from error
    parameters = {"charset": leaf.charset, **leaf.parameters}
    _finish(part, Parameterized(f"text/{leaf.subtype}", parameters), leaf)
    return part


def build_binary(leaf: BinaryLeaf) -> EnginePart:
    """Build a part from bytes the engine writes as they are.

    Raises:
        InvalidArgumentError: The bytes cannot be written in ``7bit``.
        RfcComplianceError: The type or subtype is not a token, or a header value is refused.
    """
    check_token("media type", leaf.maintype)
    check_token("media subtype", leaf.subtype)
    part: EnginePart = EmailMessage(policy=POLICY)
    try:
        part.set_content(leaf.content, leaf.maintype, leaf.subtype, cte=leaf.transfer_encoding)
    except UnicodeError as error:
        raise InvalidArgumentError(
            f'The content cannot be written in "{leaf.transfer_encoding}": {error}.'
        ) from error
    media_type = Parameterized(f"{leaf.maintype}/{leaf.subtype}", leaf.parameters)
    _finish(part, media_type, leaf)
    return part


def build_multipart(subtype: str, boundary: str, children: Sequence[EnginePart]) -> EnginePart:
    """Build a ``multipart/<subtype>`` part around ``children``, in order, split by ``boundary``.

    A child parsed from a whole message (S/MIME output) loses its ``MIME-Version``: only the
    outermost message may carry one.

    Raises:
        RfcComplianceError: The subtype is not a token, or the boundary is not 1 to 70 RFC 2046
            boundary characters ending in one that is not a space, or holds ``=?``.
    """
    check_token("media subtype", subtype)
    check_boundary(boundary)
    part: EnginePart = EmailMessage(policy=POLICY)
    part.set_raw("Content-Type", make_header("Content-Type", Parameterized(f"multipart/{subtype}")))
    part.set_boundary(boundary)
    for child in children:
        del child["MIME-Version"]
        part.attach(child)
    return part


def build_verbatim(body: bytes) -> EnginePart:
    """Build a part written as its headers, a blank line, then ``body`` exactly as it is.

    ``body`` is bytes the part must carry unchanged — what a signature covers, a message
    attached to another — every line ending in CRLF. The part has no headers until the caller
    sets them.
    """
    return VerbatimPart(body)


def build_message(headers: Sequence[tuple[str, HeaderValue]], body: EnginePart) -> EnginePart:
    """Build a whole message: ``headers`` first, then the body part's own headers and content.

    The message's headers come before the body's Content-Type, the order mail is read in; the
    body's headers are copied as they are, folding included, so a parsed body stays intact —
    but for a ``MIME-Version`` the message sets itself, which a message carries once. The body
    keeps its own list of parts: attaching to the message leaves the body as it is. A verbatim
    body is kept as the bytes it holds, and an unencoded one is copied as its bytes: the
    package's payload getter decodes them as text, which its writer then refuses as not ASCII.

    Raises:
        RfcComplianceError: As :func:`fold_header` does, for any of ``headers``.
    """
    message: EnginePart = (
        VerbatimPart(body.body) if isinstance(body, VerbatimPart) else EmailMessage(policy=POLICY)
    )
    for name, value in headers:
        add_header(message, name, value)
    has_mime_version = "MIME-Version" in message
    for name, raw_value in body.raw_items():
        if has_mime_version and name.lower() == "mime-version":
            continue
        message.set_raw(name, raw_value)
    if isinstance(body, VerbatimPart):
        return message
    if body.is_multipart():
        message.set_payload(copy.copy(body.get_payload()))
    elif str(body.get("Content-Transfer-Encoding", "")).strip().lower() in _UNENCODED:
        message.set_payload(cast("bytes", body.get_payload(decode=True)))
    else:
        message.set_payload(body.get_payload())
    message.preamble = body.preamble
    message.epilogue = body.epilogue
    return message


def set_fields(part: EnginePart, fields: Sequence[str]) -> None:
    """Replace every header of ``part`` with ``fields``, in order.

    Each field is ``Name: body`` as :func:`fold_header` writes it, without the final CRLF:
    a part's typed headers are rendered one by one, and the part carries them as written
    instead of the ones its builder wrote. A field goes through the same checks as one the
    engine folds.

    Raises:
        RfcComplianceError: A field has no header name, or a line of it is not a
            continuation of it, holds a control character, a line separator or a lone
            surrogate, or is longer than 998 octets.
    """
    _replace_headers(part, [_field(field_text) for field_text in fields])


def prepend_fields(part: EnginePart, fields: Sequence[str]) -> None:
    """Put ``fields`` before the headers ``part`` carries, which stay as they are.

    A message's own headers go before its body's, which the body's parts have folded already:
    they are not rendered a second time.

    Raises:
        RfcComplianceError: As :func:`set_fields` does, for any of ``fields``.
    """
    _replace_headers(part, [*map(_field, fields), *part.raw_items()])


def _field(field_text: str) -> tuple[str, str]:
    name, colon, rest = field_text.partition(":")
    check_name(name)
    if not colon:
        raise RfcComplianceError(f"{field_text!r} is not a header field: Name: body.")
    folded = f"{field_text}\r\n"
    check_folded(folded)
    return name, FoldedHeader(name, SOURCE_FOLD.sub("", rest).strip(" \t"), folded)


def _replace_headers(part: EnginePart, headers: list[tuple[str, str]]) -> None:
    """Make ``headers`` the whole list of the part's headers, in one step.

    The package deletes headers one name at a time, each deletion rebuilding the whole list:
    clearing a part that way costs the number of its names times the number of its headers.
    Its list — ``_headers``, which ``raw_items`` reads and ``set_raw`` appends to — is set at
    once instead.
    """
    vars(part)["_headers"] = headers


def _finish(part: EnginePart, media_type: Parameterized, leaf: TextLeaf | BinaryLeaf) -> None:
    """Give a leaf the headers the engine's content setter does not write the way we need.

    Content-Type is replaced in place (the setter's own ``set_param`` would move it below
    Content-Transfer-Encoding) and the ``MIME-Version`` a setter may add is dropped.
    """
    part.replace_header("Content-Type", make_header("Content-Type", media_type))
    if leaf.disposition is not None:
        add_header(part, "Content-Disposition", leaf.disposition)
    if leaf.content_id is not None:
        add_header(part, "Content-ID", MessageIds((leaf.content_id,)))
    del part["MIME-Version"]

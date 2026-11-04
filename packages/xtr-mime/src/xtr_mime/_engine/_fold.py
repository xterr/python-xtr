"""Header fields: each kind of value built into its header, checked and folded."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from xtr_mime.exception import MimeError, RfcComplianceError

from ._address_list import address_header
from ._addresses import to_address
from ._grammar import (
    FOLD_WIDTH,
    PACKAGE_FAILURES,
    body_of,
    check_folded,
    check_message_id,
    check_name,
    join_blank_lines,
)
from ._parameters import parameterized_header
from ._policy import DATE, POLICY, FoldedHeader
from ._unstructured import unstructured_header
from ._values import Mailbox, MessageIds, Parameterized, Path

if TYPE_CHECKING:
    from email.headerregistry import BaseHeader

    from ._policy import EnginePart
    from ._values import HeaderValue

__all__ = ["add_header", "fold_header", "header_body", "header_field", "make_header"]


def fold_header(name: str, value: HeaderValue) -> str:
    """Render one header field the way the engine writes it, folded, without the final CRLF.

    A header holding a non-ASCII local part comes back as the UTF-8 text it is written in.

    Raises:
        RfcComplianceError: ``name`` is not a header name — a colon in it among others — or
            ``value`` is not allowed in a header: a control character, an address that is not
            one or would not read back, a parameter or identifier the grammar refuses.
    """
    check_name(name)
    return _fold(name, value).removesuffix("\r\n")


def header_body(name: str, value: HeaderValue) -> str:
    """Render the body of one header field: what :func:`fold_header` writes after ``name:``.

    When the engine folds before the first word, that leading fold goes too, so the body
    always starts with its content. ``name`` may hold a colon: the body of a header a
    transport reads as a form field (``h:Sender``) is rendered too, though no field is.

    Raises:
        RfcComplianceError: ``value`` is not allowed in a header, as :func:`fold_header` says.
    """
    return _body(name, _fold(name, value))


def header_field(name: str, value: HeaderValue) -> str | None:
    """Render the field as :func:`fold_header` does, ``None`` when its body is empty.

    A header with no body is not written: the field is folded once, and both told from it.
    A name holding a colon is refused only for a header with a body, which would be written.

    Raises:
        RfcComplianceError: As :func:`fold_header` does.
    """
    folded = _fold(name, value)
    if not _body(name, folded).replace("\r\n", ""):
        return None
    check_name(name)
    return folded.removesuffix("\r\n")


def add_header(part: EnginePart, name: str, value: HeaderValue) -> None:
    """Append a header to ``part``, after the ones it has.

    Raises:
        RfcComplianceError: As :func:`fold_header` does.
    """
    check_name(name)
    part.set_raw(name, make_header(name, value))


def make_header(name: str, value: HeaderValue) -> BaseHeader | FoldedHeader:
    """Build the header the engine writes for ``value``, folded and checked.

    A field the package folds with a line of whitespace alone is kept as folded without it.

    Raises:
        RfcComplianceError: As :func:`fold_header` does.
    """
    return _made(name, value)[0]


def _made(name: str, value: HeaderValue) -> tuple[BaseHeader | FoldedHeader, str]:
    """Build the header and fold it, once: the check and the caller share the folded field."""
    try:
        header = _build_header(name, value)
        written = header.folded if isinstance(header, FoldedHeader) else header.fold(policy=POLICY)
    except MimeError:
        raise
    except PACKAGE_FAILURES as error:
        raise RfcComplianceError(f"The {name} header cannot be written: {error}.") from error
    folded = join_blank_lines(written)
    check_folded(folded)
    if folded != written:
        header = FoldedHeader(name, str(header), folded)
    return header, folded


def _fold(name: str, value: HeaderValue) -> str:
    return _made(name, value)[1]


def _body(name: str, folded: str) -> str:
    return body_of(name, folded).removeprefix("\r\n").removeprefix(" ")


def _build_header(name: str, value: HeaderValue) -> BaseHeader | FoldedHeader:
    match value:
        case str():
            return unstructured_header(name, value)
        case datetime():
            return DATE(name, value)
        case Parameterized():
            return parameterized_header(name, value)
        case MessageIds():
            return _identifier_header(name, value.ids)
        case Path():
            return _path_header(name, value.address)
        case _:
            return address_header(name, value)


def _identifier_header(name: str, ids: tuple[str, ...]) -> FoldedHeader:
    """Write ``<id>`` tokens, folded only between two of them.

    The engine would turn an id too long for a line into encoded words, which no reader
    matches against a Message-ID; a long id stays whole on its line instead, as RFC 5322
    allows up to 998 characters.
    """
    if not ids:
        raise RfcComplianceError(f"The {name} header needs at least one identifier.")
    for identifier in ids:
        check_message_id(identifier)
    tokens = [f"<{identifier}>" for identifier in ids]
    lines = [f"{name}: {tokens[0]}"]
    for token in tokens[1:]:
        if len(lines[-1]) + 1 + len(token) > FOLD_WIDTH:
            lines.append(f" {token}")
        else:
            lines[-1] += f" {token}"
    return FoldedHeader(name, " ".join(tokens), "\r\n".join(lines) + "\r\n")


def _path_header(name: str, address: str) -> FoldedHeader:
    """Write ``<address>``: the domain in punycode, a non-ASCII local part as raw UTF-8.

    The address goes through the same checks as one in an address header; a path has no name.
    """
    path = f"<{to_address(Mailbox('', address)).addr_spec}>"
    return FoldedHeader(name, path, f"{name}: {path}\r\n")

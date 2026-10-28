"""The one place xtr-mime talks to Python's ``email`` package.

Everything that ends up on the wire — encoded words, folding, parameter encoding, transfer
encodings, boundaries laid out between parts — is the ``email`` package's work. The rest of
xtr-mime keeps its own typed model and hands it to the functions here, so no ``email`` type
leaks into a public signature and a change in the package's behaviour has one place to land.

Two of the package's habits are worked around rather than accepted:

* an international domain is punycoded before it reaches an address header, because the
  package writes a raw Unicode domain as an encoded word no server accepts (CPython
  gh-83938);
* trees are built from plain parts with an explicit boundary, never with the package's
  ``add_related``/``add_alternative`` helpers (they decide the nesting themselves), and the
  ``MIME-Version`` header the package's content setter adds is taken off every part — only a
  whole message carries it, and xtr-mime writes that one itself.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from email import policy as email_policy
from email.errors import HeaderParseError
from email.generator import BytesGenerator
from email.headerregistry import (
    Address,
    AddressHeader,
    ContentDispositionHeader,
    ContentTypeHeader,
    DateHeader,
    Group,
    HeaderRegistry,
    UnstructuredHeader,
)
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import quote
from typing import TYPE_CHECKING, Final, Literal, TypeAlias, cast, final

import idna

from .exception import InvalidArgumentError, RfcComplianceError

if TYPE_CHECKING:
    from email.headerregistry import BaseHeader

__all__ = [
    "POLICY",
    "BinaryLeaf",
    "EnginePart",
    "HeaderValue",
    "Mailbox",
    "MailboxGroup",
    "Parameterized",
    "TextLeaf",
    "TransferEncoding",
    "add_header",
    "build_binary",
    "build_message",
    "build_multipart",
    "build_text",
    "encode_idn_address",
    "fold_header",
    "header_body",
    "parse",
    "render",
    "to_bytes",
    "to_string",
]

POLICY: Final = email_policy.SMTP.clone(max_line_length=76)
"""CRLF line ends and 76-column folding: what SMTP expects and what mail clients read."""

# Quoted: the class is generic only in its type stubs, not at runtime. It is the parser's
# class too, so a parsed message and a built one are the same kind of value.
EnginePart: TypeAlias = "EmailMessage[str, str]"
"""A part or a whole message as the engine holds it; never seen outside xtr-mime."""

TransferEncoding: TypeAlias = Literal["7bit", "8bit", "quoted-printable", "base64"]

_UNSTRUCTURED: Final = HeaderRegistry(default_class=UnstructuredHeader, use_default_map=False)
_DATE: Final = HeaderRegistry(default_class=DateHeader, use_default_map=False)
_ADDRESS: Final = HeaderRegistry(default_class=AddressHeader, use_default_map=False)
# The stubs give these two a class-level `max_count` the registry's parameter type rejects;
# at runtime the registry takes any header class, so they are passed as the type it names.
_CONTENT_TYPE: Final = HeaderRegistry(
    default_class=cast("type[UnstructuredHeader]", ContentTypeHeader), use_default_map=False
)
_PARAMETERIZED: Final = HeaderRegistry(
    default_class=cast("type[UnstructuredHeader]", ContentDispositionHeader),
    use_default_map=False,
)


@final
@dataclass(frozen=True, slots=True)
class Mailbox:
    """One address, with the name shown next to it (empty for none)."""

    display_name: str
    address: str


@final
@dataclass(frozen=True, slots=True)
class MailboxGroup:
    """A named list of addresses, written ``name: a, b;``."""

    display_name: str
    mailboxes: tuple[Mailbox, ...]


@final
@dataclass(frozen=True, slots=True)
class Parameterized:
    """A header value followed by ``; name=value`` parameters, as Content-Type has."""

    value: str
    parameters: Mapping[str, str] = field(default_factory=dict[str, str])


HeaderValue: TypeAlias = str | datetime | Parameterized | Sequence[Mailbox | MailboxGroup]
"""What a header holds; the kind decides how the engine encodes it."""


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class TextLeaf:
    """A text part: the engine encodes ``content`` in ``charset``, then in the transfer encoding.

    ``parameters`` are added to Content-Type after ``charset``.
    """

    content: str
    subtype: str
    charset: str
    transfer_encoding: TransferEncoding
    parameters: Mapping[str, str] = field(default_factory=dict[str, str])
    disposition: Parameterized | None = None
    content_id: str | None = None


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class BinaryLeaf:
    """A part whose bytes are written as they are, in the transfer encoding asked for.

    Also a text part with no charset: its bytes are not the engine's to interpret.
    """

    content: bytes
    maintype: str
    subtype: str
    transfer_encoding: TransferEncoding
    parameters: Mapping[str, str] = field(default_factory=dict[str, str])
    disposition: Parameterized | None = None
    content_id: str | None = None


@final
class _ChunkSink:
    """Collects what the generator writes, so rendering can hand the message out in pieces."""

    __slots__ = ("chunks",)

    def __init__(self) -> None:
        self.chunks: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.chunks.append(data)


def encode_idn_address(address: str) -> str:
    """Write the domain of ``address`` in ASCII (punycode) when it is not already.

    An ASCII domain is left alone, case included: only a domain that needs IDNA goes through
    it, and the local part is never touched (it travels as is, or not at all, under SMTPUTF8).

    Raises:
        RfcComplianceError: The domain is not a valid international domain name.
    """
    local, at, domain = address.rpartition("@")
    if not at or domain.isascii():
        return address
    try:
        encoded = idna.encode(domain, uts46=True, std3_rules=True).decode("ascii")
    except idna.IDNAError as error:
        raise RfcComplianceError(
            f'The domain "{domain}" of "{address}" cannot be written in ASCII: {error}.'
        ) from error
    return f"{local}@{encoded}"


def fold_header(name: str, value: HeaderValue) -> str:
    """Render one header field the way the engine writes it, folded, without the final CRLF.

    Raises:
        RfcComplianceError: An address in ``value`` is not one.
    """
    return _make_header(name, value).fold(policy=POLICY).removesuffix("\r\n")


def header_body(name: str, value: HeaderValue) -> str:
    """Render the body of one header field: :func:`fold_header` without ``name:``.

    When the engine folds before the first word, that leading fold goes too, so the body
    always starts with its content.
    """
    body = fold_header(name, value)[len(name) + 1 :]
    return body.removeprefix("\r\n").removeprefix(" ")


def add_header(part: EnginePart, name: str, value: HeaderValue) -> None:
    """Append a header to ``part``, after the ones it has."""
    part.set_raw(name, _make_header(name, value))


def build_text(leaf: TextLeaf) -> EnginePart:
    """Build a text part; its body always ends with a line break, the engine adds one.

    Raises:
        InvalidArgumentError: Python knows no such charset, or the content cannot be written
            in it or in the transfer encoding.
    """
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
    """
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
    """
    part: EnginePart = EmailMessage(policy=POLICY)
    part.set_raw(
        "Content-Type", _make_header("Content-Type", Parameterized(f"multipart/{subtype}"))
    )
    part.set_boundary(boundary)
    for child in children:
        del child["MIME-Version"]
        part.attach(child)
    return part


def build_message(headers: Sequence[tuple[str, HeaderValue]], body: EnginePart) -> EnginePart:
    """Build a whole message: ``headers`` first, then the body part's own headers and content.

    The message's headers come before the body's Content-Type, the order mail is read in; the
    body's headers are copied as they are, folding included, so a parsed body stays intact.
    """
    message: EnginePart = EmailMessage(policy=POLICY)
    for name, value in headers:
        add_header(message, name, value)
    for name, raw_value in body.raw_items():
        message.set_raw(name, raw_value)
    message.set_payload(body.get_payload())
    message.preamble = body.preamble
    message.epilogue = body.epilogue
    return message


def render(part: EnginePart) -> Iterator[bytes]:
    """Render ``part`` as the bytes a mail server accepts, in the pieces the engine writes."""
    sink = _ChunkSink()
    BytesGenerator(sink, mangle_from_=False, policy=POLICY).flatten(part)
    yield from sink.chunks


def to_bytes(part: EnginePart) -> bytes:
    """Render ``part`` in one piece."""
    return b"".join(render(part))


def to_string(part: EnginePart) -> str:
    """Render ``part`` as text; bytes that are not UTF-8 (an 8bit body) survive as surrogates.

    ``to_string(part).encode("utf-8", "surrogateescape") == to_bytes(part)``, always.
    """
    return to_bytes(part).decode("utf-8", "surrogateescape")


def parse(data: bytes) -> EnginePart:
    """Read a rendered message (S/MIME output, a test's expectation) back into a part tree."""
    return BytesParser(policy=POLICY).parsebytes(data)


def _make_header(name: str, value: HeaderValue) -> BaseHeader:
    match value:
        case str():
            return _UNSTRUCTURED(name, value)
        case datetime():
            return _DATE(name, value)
        case Parameterized():
            registry = _CONTENT_TYPE if name.lower() == "content-type" else _PARAMETERIZED
            return registry(name, _join_parameters(value))
        case _:
            return _ADDRESS(name, [_to_engine_address(item) for item in value])


def _join_parameters(value: Parameterized) -> str:
    parameters = (f'{key}="{quote(item)}"' for key, item in value.parameters.items())
    return "; ".join((value.value, *parameters))


def _to_engine_address(item: Mailbox | MailboxGroup) -> Address | Group:
    match item:
        case Mailbox():
            return _to_address(item)
        case MailboxGroup():
            return Group(item.display_name, [_to_address(member) for member in item.mailboxes])


def _to_address(mailbox: Mailbox) -> Address:
    encoded = encode_idn_address(mailbox.address)
    try:
        return Address(mailbox.display_name, addr_spec=encoded)
    except (ValueError, HeaderParseError) as error:
        raise RfcComplianceError(
            f'"{mailbox.address}" is not a valid email address: {error}.'
        ) from error


def _finish(part: EnginePart, media_type: Parameterized, leaf: TextLeaf | BinaryLeaf) -> None:
    """Give a leaf the headers the engine's content setter does not write the way we need.

    Content-Type is replaced in place (the setter's own ``set_param`` would move it below
    Content-Transfer-Encoding) and the ``MIME-Version`` a setter may add is dropped.
    """
    part.replace_header("Content-Type", _make_header("Content-Type", media_type))
    if leaf.disposition is not None:
        add_header(part, "Content-Disposition", leaf.disposition)
    if leaf.content_id is not None:
        add_header(part, "Content-ID", leaf.content_id)
    del part["MIME-Version"]

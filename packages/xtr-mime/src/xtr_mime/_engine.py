"""The one place xtr-mime talks to Python's ``email`` package.

Everything that ends up on the wire — encoded words, folding, parameter encoding, transfer
encodings, boundaries laid out between parts — is the ``email`` package's work. The rest of
xtr-mime keeps its own typed model and hands it to the functions here, so no ``email`` type
leaks into a public signature and a change in the package's behaviour has one place to land.

Some of the package's habits are worked around rather than accepted:

* an international domain is punycoded before it reaches an address header, because the
  package writes a raw Unicode domain as an encoded word no server accepts (CPython
  gh-83938);
* a non-ASCII local part, which the package's address reader refuses, is written as raw
  UTF-8 (RFC 6532) — the form an SMTPUTF8 session carries — in that header only;
* message identifiers are written as ``<id>`` tokens folded between ids, never as the encoded
  words the package makes of a long unstructured value;
* trees are built from plain parts with an explicit boundary, never with the package's
  ``add_related``/``add_alternative`` helpers (they decide the nesting themselves), and the
  ``MIME-Version`` header the package's content setter adds is taken off every part — only a
  whole message carries it, and xtr-mime writes that one itself.

Header injection is refused here, not left to the package: whether it keeps a line break out
of a header depends on its patch level (the CVE-2024-6923 fix is missing from 3.11.0-3.11.9
and 3.12.0-3.12.4). Every value is refused if it holds a control character other than TAB, a
line separator or a lone surrogate; every field written — a parsed part's included, when the
message is rendered — is checked to continue only on lines starting with a space or a tab, to
hold none of those characters and to keep its lines within 998 octets; and an address header
must read back to the addresses it was given.

A header must also read back to the text it was given, as a mail client reads RFC 2047 — not
as the package's own lenient reader does. Python 3.11 and 3.12.0 fold a long name so a client
joins two of its words, and the package decodes an encoded word found in a value; when what
the package writes does not read back, the engine writes the field itself from the package's
encoded words (``email.header.Header``), and refuses it if that does not read back either. A
failure of the package on a value it cannot handle comes out as this package's own error.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from email import policy as email_policy
from email.errors import HeaderParseError, MessageError, NonASCIILocalPartDefect
from email.generator import BytesGenerator
from email.header import Header
from email.headerregistry import (
    Address,
    AddressHeader,
    ContentDispositionHeader,
    ContentTypeHeader,
    DateHeader,
    Group,
    HeaderRegistry,
    ParameterizedMIMEHeader,
    UnstructuredHeader,
)
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import quote
from typing import TYPE_CHECKING, Final, Literal, TypeAlias, cast, final

import idna

from ._header_reader import ReadGroup, read_address_list, read_unstructured
from .exception import InvalidArgumentError, MimeError, MimeRuntimeError, RfcComplianceError

if TYPE_CHECKING:
    from email.headerregistry import BaseHeader
    from typing import Self

__all__ = [
    "POLICY",
    "BinaryLeaf",
    "EnginePart",
    "HeaderValue",
    "Mailbox",
    "MailboxGroup",
    "MessageIds",
    "Parameterized",
    "Path",
    "TextLeaf",
    "TransferEncoding",
    "add_header",
    "build_binary",
    "build_message",
    "build_multipart",
    "build_text",
    "check_message_id",
    "encode_idn_address",
    "fold_header",
    "header_body",
    "parse",
    "render",
    "to_bytes",
    "to_string",
]

_FOLD_WIDTH: Final = 76
# RFC 5322, 2.1.1: the hard limit on a line, whatever folding allows.
_MAX_LINE_LENGTH: Final = 998

POLICY: Final = email_policy.SMTP.clone(max_line_length=_FOLD_WIDTH)
"""CRLF line ends and 76-column folding: what SMTP expects and what mail clients read."""

_UTF8_POLICY: Final = POLICY.clone(utf8=True)

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

# Every C0 control but TAB, DEL, the C1 controls (NEL among them), the line and paragraph
# separators and a lone surrogate: a line break would start a new header, some readers end a
# line at any of the others, and a lone surrogate is a byte that was never text.
_FORBIDDEN: Final = re.compile(r"[\x00-\x08\x0a-\x1f\x7f-\x9f\u2028\u2029\ud800-\udfff]")
# RFC 5322, 2.2: printable ASCII. A colon is kept — a reader ends the name at the first one —
# so an API reading prefixed names (``h:Sender``) gets them as given.
_FIELD_NAME: Final = re.compile(r"[!-~]+")
# RFC 2045, 5.1: printable ASCII but space and the tspecials.
_TOKEN: Final = re.compile(r"[!#$%&'*+\-.^_`{|}~0-9A-Za-z]+")
# RFC 2231, 7: a token without "*", "'" and "%", which carry the parameter's own encoding.
_PARAMETER_NAME: Final = re.compile(r"[!#$&+\-.^_`{|}~0-9A-Za-z]+")
# RFC 2046, 5.1.1: 1 to 70 of its bchars, the last one not a space.
_BOUNDARY: Final = re.compile(r"[0-9A-Za-z'()+_,\-./:=? ]{0,69}[0-9A-Za-z'()+_,\-./:=?]")
# RFC 5322, 3.6.4: id-left "@" id-right, the left a dot-atom or a quoted string, the right a
# dot-atom or a literal. Nothing in it may be read as the end of the id — no angle bracket —
# and a quoted pair is refused, as the engine reads ``\<`` back as ``<``: another id.
_ATEXT: Final = r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]"
_DOT_ATOM: Final = rf"{_ATEXT}+(?:\.{_ATEXT}+)*"
_MESSAGE_ID: Final = re.compile(
    rf'(?:{_DOT_ATOM}|"[!#-;=?-\[\]-~]+")@(?:{_DOT_ATOM}|\[[!-;=?-Z^-~]*\])'
)
# What the engine's readers take for an encoded word, which they decode instead of showing.
_ENCODED_WORD: Final = re.compile(r"=\?.*\?=", re.DOTALL)
# A fold in a header as the parser keeps it, from a source with CRLF or bare LF line ends.
_SOURCE_FOLD: Final = re.compile(r"\r?\n(?=[ \t])")
# Words a name is written as when the engine writes it unquoted: atext, non-ASCII included
# (RFC 6532), one space apart.
_ATOM: Final = r"[^\x00-\x20\x7f()<>\[\]:;@\\,.\"]+"
_PHRASE: Final = re.compile(rf"{_ATOM}(?: {_ATOM})*")

# What the package raises on a value it cannot handle, rather than an error of its own.
_PACKAGE_FAILURES: Final = (
    AttributeError,
    IndexError,
    KeyError,
    LookupError,
    RecursionError,
    TypeError,
    ValueError,
    MessageError,
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


@final
@dataclass(frozen=True, slots=True)
class MessageIds:
    """Message identifiers, without their angle brackets, as Message-ID and References hold."""

    ids: tuple[str, ...]


@final
@dataclass(frozen=True, slots=True)
class Path:
    """One bare address, written ``<address>``, as Return-Path holds."""

    address: str


HeaderValue: TypeAlias = (
    str | datetime | Parameterized | MessageIds | Path | Sequence[Mailbox | MailboxGroup]
)
"""What a header holds; the kind decides how the engine encodes it."""


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class TextLeaf:
    """A text part: the engine encodes ``content`` in ``charset``, then in the transfer encoding.

    ``parameters`` are added to Content-Type after ``charset``; ``content_id`` is the bare
    identifier, written ``<content_id>``.
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
    ``content_id`` is the bare identifier, written ``<content_id>``.
    """

    content: bytes
    maintype: str
    subtype: str
    transfer_encoding: TransferEncoding
    parameters: Mapping[str, str] = field(default_factory=dict[str, str])
    disposition: Parameterized | None = None
    content_id: str | None = None


@final
class _FoldedHeader(str):  # noqa: SLOT000 -- a str subclass cannot have non-empty __slots__
    """A header field xtr-mime has folded itself, which the engine writes without refolding.

    The engine's policy hands any header value that has a ``name`` to its ``fold``. What this
    returns carries non-ASCII text as surrogate-escaped bytes — the engine's own form for bytes
    it must write untouched — so a raw UTF-8 header reaches the wire as UTF-8.
    """

    def __new__(cls, name: str, body: str, folded: str) -> Self:
        """Make the string value ``body``, the header's value as read."""
        del name, folded
        return super().__new__(cls, body)

    def __init__(self, name: str, body: str, folded: str) -> None:
        """Keep ``name`` and ``folded``, the whole field as written, ending in CRLF."""
        super().__init__()
        del body
        self.name: str = name
        self.folded: str = folded

    def fold(self, *, policy: object) -> str:
        """Return the field as folded, whatever the policy: it was folded for this one."""
        del policy
        return self.folded.encode("utf-8", "surrogateescape").decode("ascii", "surrogateescape")


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
    it. The local part is never touched: a non-ASCII one cannot be written in ASCII, so the
    header holding it is written in raw UTF-8 and the message needs an SMTPUTF8 session.

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

    A header holding a non-ASCII local part comes back as the UTF-8 text it is written in.

    Raises:
        RfcComplianceError: ``name`` is not a header name, or ``value`` is not allowed in a
            header: a control character, an address that is not one or would not read back,
            a parameter or identifier the grammar refuses.
    """
    header = _make_header(name, value)
    if isinstance(header, _FoldedHeader):
        return header.folded.removesuffix("\r\n")
    return header.fold(policy=POLICY).removesuffix("\r\n")


def header_body(name: str, value: HeaderValue) -> str:
    """Render the body of one header field: :func:`fold_header` without ``name:``.

    When the engine folds before the first word, that leading fold goes too, so the body
    always starts with its content.
    """
    body = fold_header(name, value)[len(name) + 1 :]
    return body.removeprefix("\r\n").removeprefix(" ")


def add_header(part: EnginePart, name: str, value: HeaderValue) -> None:
    """Append a header to ``part``, after the ones it has.

    Raises:
        RfcComplianceError: As :func:`fold_header` does.
    """
    part.set_raw(name, _make_header(name, value))


def build_text(leaf: TextLeaf) -> EnginePart:
    """Build a text part; its body always ends with a line break, the engine adds one.

    Raises:
        InvalidArgumentError: Python knows no such charset, or the content cannot be written
            in it or in the transfer encoding.
        RfcComplianceError: The subtype or the charset is not a token, or a header value is
            refused.
    """
    _check_token("media subtype", leaf.subtype)
    _check_token("charset", leaf.charset)
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
    _check_token("media type", leaf.maintype)
    _check_token("media subtype", leaf.subtype)
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
    _check_token("media subtype", subtype)
    # "=?" opens an encoded word: the engine would take such a boundary for one and replace it.
    if not _BOUNDARY.fullmatch(boundary) or "=?" in boundary:
        raise RfcComplianceError(
            f"The boundary {boundary!r} is not 1 to 70 RFC 2046 boundary characters ending in "
            'one that is not a space, without "=?".'
        )
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
    body's headers are copied as they are, folding included, so a parsed body stays intact —
    but for a ``MIME-Version`` the message sets itself, which a message carries once. The body
    keeps its own list of parts: attaching to the message leaves the body as it is.

    Raises:
        RfcComplianceError: As :func:`fold_header` does, for any of ``headers``.
    """
    message: EnginePart = EmailMessage(policy=POLICY)
    for name, value in headers:
        add_header(message, name, value)
    has_mime_version = "MIME-Version" in message
    for name, raw_value in body.raw_items():
        if has_mime_version and name.lower() == "mime-version":
            continue
        message.set_raw(name, raw_value)
    message.set_payload(copy.copy(body.get_payload()))
    message.preamble = body.preamble
    message.epilogue = body.epilogue
    return message


def render(part: EnginePart) -> Iterator[bytes]:
    """Render ``part`` as the bytes a mail server accepts, in the pieces the engine writes.

    Every header of every part is checked as it will be written first, those of a parsed part
    included: a header the engine did not build itself may hold what one it builds may not.

    Raises:
        RfcComplianceError: A header is refused: its name is not one, or what is written of
            it holds a control character, a line separator or a lone surrogate, starts a line
            of its own or has a line longer than 998 octets.
        MimeRuntimeError: The engine fails to write the part.
    """
    for sub_part in part.walk():
        for name, value in sub_part.raw_items():
            _check_written(name, value)
    sink = _ChunkSink()
    try:
        BytesGenerator(sink, mangle_from_=False, policy=POLICY).flatten(part)
    except _PACKAGE_FAILURES as error:
        raise MimeRuntimeError(f"The message cannot be written: {error}.") from error
    yield from sink.chunks


def to_bytes(part: EnginePart) -> bytes:
    """Render ``part`` in one piece.

    Raises:
        RfcComplianceError: As :func:`render` does.
        MimeRuntimeError: As :func:`render` does.
    """
    return b"".join(render(part))


def to_string(part: EnginePart) -> str:
    """Render ``part`` as text; bytes that are not UTF-8 (an 8bit body) survive as surrogates.

    ``to_string(part).encode("utf-8", "surrogateescape") == to_bytes(part)``, always.

    Raises:
        RfcComplianceError: As :func:`render` does.
        MimeRuntimeError: As :func:`render` does.
    """
    return to_bytes(part).decode("utf-8", "surrogateescape")


def parse(data: bytes) -> EnginePart:
    """Read a rendered message (S/MIME output, a test's expectation) back into a part tree.

    Raises:
        MimeRuntimeError: The parts are nested deeper than the engine's reader can follow, or
            the reader fails on the bytes.
    """
    try:
        return BytesParser(policy=POLICY).parsebytes(data)
    except RecursionError as error:
        raise MimeRuntimeError("The message is nested too deeply to be read.") from error
    except _PACKAGE_FAILURES as error:
        raise MimeRuntimeError(f"The message cannot be read: {error}.") from error


def check_message_id(identifier: str) -> None:
    """Refuse ``identifier`` unless it is an RFC 5322 msg-id, without its angle brackets.

    ``id-left@id-right``: the left a dot-atom or a quoted string, the right a dot-atom or a
    literal, in ASCII. No angle bracket and no quoted pair: a reader would end the id at one,
    or read the other back without its backslash.

    Raises:
        RfcComplianceError: ``identifier`` is not one.
    """
    if not _MESSAGE_ID.fullmatch(identifier):
        raise RfcComplianceError(
            f"{identifier!r} is not a message identifier: id-left@id-right (RFC 5322, 3.6.4), "
            "without spaces, angle brackets or quoted pairs."
        )


def _make_header(name: str, value: HeaderValue) -> BaseHeader | _FoldedHeader:
    _check_name(name)
    try:
        header = _build_header(name, value)
        folded = header.folded if isinstance(header, _FoldedHeader) else header.fold(policy=POLICY)
    except MimeError:
        raise
    except _PACKAGE_FAILURES as error:
        raise RfcComplianceError(f"The {name} header cannot be written: {error}.") from error
    _check_folded(folded)
    return header


def _check_name(name: str) -> None:
    if not _FIELD_NAME.fullmatch(name):
        raise RfcComplianceError(f"{name!r} is not a header name: printable ASCII, no space.")


def _check_written(name: str, value: str) -> None:
    """Check one header of a part the way the generator will write it."""
    _check_name(name)
    if not hasattr(value, "name"):
        # A parsed part's header holds the bytes the parser read, undecoded: it is checked as
        # the text they are, its folds taken out.
        try:
            text = value.encode("utf-8", "surrogateescape").decode("utf-8", "surrogateescape")
        except UnicodeError as error:
            raise RfcComplianceError(f"The {name} header is not text: {error}.") from error
        _refuse_forbidden(f"The {name} header", _SOURCE_FOLD.sub("", text))
    try:
        written = POLICY.fold_binary(name, value)
    except _PACKAGE_FAILURES as error:
        raise RfcComplianceError(f"The {name} header cannot be written: {error}.") from error
    _check_folded(written.decode("utf-8", "surrogateescape"))


def _build_header(name: str, value: HeaderValue) -> BaseHeader | _FoldedHeader:
    match value:
        case str():
            return _unstructured_header(name, value)
        case datetime():
            return _DATE(name, value)
        case Parameterized():
            return _parameterized_header(name, value)
        case MessageIds():
            return _identifier_header(name, value.ids)
        case Path():
            return _path_header(name, value.address)
        case _:
            return _address_header(name, value)


def _unstructured_header(name: str, value: str) -> BaseHeader | _FoldedHeader:
    _refuse_forbidden(f"The {name} header", value)
    header = _UNSTRUCTURED(name, value)
    # The engine reads an encoded word in the value as one: what it decodes to may hold what
    # the value itself did not.
    _refuse_forbidden(f"The decoded {name} header", str(header))
    if _reads_back_as(name, header.fold(policy=POLICY), value):
        return header
    encoded = Header(value, "utf-8", maxlinelen=_FOLD_WIDTH, header_name=name)
    folded = f"{name}: " + encoded.encode(linesep="\r\n") + "\r\n"
    if not _reads_back_as(name, folded, value):
        raise RfcComplianceError(
            f"The {name} header would not read back to the text it was given: {folded!r}."
        )
    return _FoldedHeader(name, value, folded)


def _reads_back_as(name: str, folded: str, value: str) -> bool:
    # Whitespace around the value reads back if it went into an encoded word, and is dropped
    # if it did not; either reading is the value.
    try:
        return read_unstructured(_body_of(name, folded)) in {value, value.strip(" \t")}
    except ValueError:
        return False


def _body_of(name: str, folded: str) -> str:
    return folded[len(name) + 1 :].removesuffix("\r\n")


def _parameterized_header(name: str, value: Parameterized) -> BaseHeader:
    _check_parameterized(name, value)
    registry = _CONTENT_TYPE if name.lower() == "content-type" else _PARAMETERIZED
    header = registry(name, _join_parameters(value))
    # The engine decodes an encoded word in a quoted parameter, which may hold what the value
    # itself did not.
    for key, item in _parameters_of(header).items():
        _refuse_forbidden(f"The decoded {key} parameter", str(item))
    return header


def _refuse_forbidden(what: str, value: str) -> None:
    if _FORBIDDEN.search(value):
        raise RfcComplianceError(
            f"{what} must not contain a control character, a line separator or a lone "
            f"surrogate: {value!r}."
        )


def _check_folded(folded: str) -> None:
    """Refuse a folded field any line of which would start a header of its own, or break one.

    Run on everything the engine folds, so a line break that slips through it — as one did
    before CVE-2024-6923 was fixed — never reaches the wire, nor a character some reader ends
    a line at, nor a line longer than RFC 5322 allows.
    """
    lines = folded.removesuffix("\r\n").split("\r\n")
    if (
        not folded.endswith("\r\n")
        or any("\r" in line or "\n" in line for line in lines)
        or not all(line.startswith((" ", "\t")) for line in lines[1:])
    ):
        raise RfcComplianceError(
            f"A folded header has a line that is not a continuation of it: {folded!r}."
        )
    for line in lines:
        _refuse_forbidden("A folded header", line)
        if len(line.encode("utf-8", "surrogateescape")) > _MAX_LINE_LENGTH:
            raise RfcComplianceError(
                f"A folded header has a line longer than {_MAX_LINE_LENGTH} octets: {line[:80]!r}…"
            )


def _check_token(what: str, token: str) -> None:
    if not _TOKEN.fullmatch(token):
        raise RfcComplianceError(f"The {what} {token!r} is not a token.")


def _check_parameterized(name: str, value: Parameterized) -> None:
    if name.lower() == "content-type":
        maintype, slash, subtype = value.value.partition("/")
        if not (slash and _TOKEN.fullmatch(maintype) and _TOKEN.fullmatch(subtype)):
            raise RfcComplianceError(f"{value.value!r} is not a media type: type/subtype.")
    else:
        _check_token(f"{name} value", value.value)
    for key, item in value.parameters.items():
        if not _PARAMETER_NAME.fullmatch(key):
            raise RfcComplianceError(f"{key!r} is not a parameter name: an RFC 2231 token.")
        _refuse_forbidden(f"The {key} parameter", item)


def _join_parameters(value: Parameterized) -> str:
    parameters = (f'{key}="{quote(item)}"' for key, item in value.parameters.items())
    return "; ".join((value.value, *parameters))


def _identifier_header(name: str, ids: tuple[str, ...]) -> _FoldedHeader:
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
        if len(lines[-1]) + 1 + len(token) > _FOLD_WIDTH:
            lines.append(f" {token}")
        else:
            lines[-1] += f" {token}"
    return _FoldedHeader(name, " ".join(tokens), "\r\n".join(lines) + "\r\n")


def _path_header(name: str, address: str) -> _FoldedHeader:
    """Write ``<address>``: the domain in punycode, a non-ASCII local part as raw UTF-8.

    The address goes through the same checks as one in an address header; a path has no name.
    """
    path = f"<{_to_address(Mailbox('', address)).addr_spec}>"
    return _FoldedHeader(name, path, f"{name}: {path}\r\n")


def _address_header(
    name: str, value: Sequence[Mailbox | MailboxGroup]
) -> BaseHeader | _FoldedHeader:
    items = [_to_engine_address(item) for item in value]
    header = _ADDRESS(name, items)
    utf8 = any(not address.username.isascii() for address in _addresses_of(items))
    written = header.fold(policy=_UTF8_POLICY if utf8 else POLICY)
    folded = (
        written
        if _names_read_back(name, items, written)
        else _write_address_list(name, items, utf8=utf8)
    )
    if not _names_read_back(name, items, folded):
        raise RfcComplianceError(
            f"The {name} header would not read back to the names it was given: {folded!r}."
        )
    _check_reads_back(name, items, folded)
    if folded == written and not utf8:
        return header
    return _FoldedHeader(name, str(header), folded)


def _names_read_back(name: str, items: Sequence[Address | Group], folded: str) -> bool:
    """Tell whether a mail client reads the groups and names ``items`` hold in ``folded``."""
    given: list[ReadGroup] = [
        (
            (item.display_name or "").strip(" \t"),
            [address.display_name.strip(" \t") for address in item.addresses],
        )
        if isinstance(item, Group)
        else (None, [item.display_name.strip(" \t")])
        for item in items
    ]
    try:
        return read_address_list(_body_of(name, folded)) == given
    except ValueError:
        return False


def _write_address_list(name: str, items: Sequence[Address | Group], *, utf8: bool) -> str:
    """Write an address header the engine's folding would not write faithfully.

    A name is written as atoms, as a quoted string, or — when not ASCII and the header is not
    raw UTF-8 — as the package's legacy encoded words, which keep every space inside a word.
    The field is folded between words, at 76 columns where a word allows.
    """
    words: list[str] = []
    for position, item in enumerate(items):
        if position:
            words[-1] += ","
        if isinstance(item, Group):
            words += _phrase_words(item.display_name or "", utf8=utf8) or [""]
            words[-1] += ":"
            for index, member in enumerate(item.addresses):
                if index:
                    words[-1] += ","
                words += _mailbox_words(member, utf8=utf8)
            words[-1] += ";"
        else:
            words += _mailbox_words(item, utf8=utf8)
    lines = [f"{name}:"]
    for word in words:
        if len(lines[-1]) + 1 + len(word) > _FOLD_WIDTH:
            lines.append(f" {word}")
        else:
            lines[-1] += f" {word}"
    return "\r\n".join(lines) + "\r\n"


def _mailbox_words(address: Address, *, utf8: bool) -> list[str]:
    phrase = _phrase_words(address.display_name, utf8=utf8)
    return [*phrase, f"<{address.addr_spec}>"] if phrase else [address.addr_spec]


def _phrase_words(display_name: str, *, utf8: bool) -> list[str]:
    text = display_name.strip(" \t")
    if not text:
        return []
    if utf8 or text.isascii():
        return text.split(" ") if _PHRASE.fullmatch(text) else [f'"{quote(text)}"']
    return Header(text, "utf-8", maxlinelen=_FOLD_WIDTH - 1).encode(linesep="\n").split()


def _addresses_of(items: Sequence[Address | Group]) -> Iterator[Address]:
    for item in items:
        if isinstance(item, Group):
            yield from item.addresses
        else:
            yield item


def _check_reads_back(name: str, items: Sequence[Address | Group], folded: str) -> None:
    """Refuse a header that a reader would take for other addresses than the ones given.

    The engine reads the header it writes back into words before folding them, so what it
    folds is its reading of the value, not the value: a name it decoded from an encoded word
    comes out as plain text, where it reads as an address. Names are kept literal before they
    get here; this catches whatever other reading the engine may make of a value.
    """
    read = _as_address_header(_ADDRESS(name, folded[len(name) + 1 :].replace("\r\n", "")))
    given = [
        (True, tuple(a.addr_spec for a in item.addresses))
        if isinstance(item, Group)
        else (False, (item.addr_spec,))
        for item in items
    ]
    found = [
        (group.display_name is not None, tuple(a.addr_spec for a in group.addresses))
        for group in read.groups
    ]
    if found != given:
        raise RfcComplianceError(
            f"The {name} header would not read back to the addresses it was given: {folded!r}."
        )


def _check_literal_name(display_name: str) -> None:
    """Refuse a name the engine would decode rather than write as the text it is.

    The engine reads an encoded word in a name as one and writes the decoded text, unquoted —
    where it can read as an address (or, in a group name, crash the engine's folder).
    """
    _refuse_forbidden("A display name", display_name)
    if _ENCODED_WORD.search(display_name):
        raise RfcComplianceError(
            f"The display name {display_name!r} holds an encoded word: a reader would show it "
            "decoded, not as the literal text it is."
        )


def _to_engine_address(item: Mailbox | MailboxGroup) -> Address | Group:
    match item:
        case Mailbox():
            return _to_address(item)
        case MailboxGroup():
            _check_literal_name(item.display_name)
            return Group(item.display_name, [_to_address(member) for member in item.mailboxes])


def _to_address(mailbox: Mailbox) -> Address:
    _check_literal_name(mailbox.display_name)
    _refuse_forbidden("An email address", mailbox.address)
    if "=?" in mailbox.address:
        raise RfcComplianceError(
            f'"{mailbox.address}" holds an encoded word: the engine would decode it into '
            "another address."
        )
    encoded = encode_idn_address(mailbox.address)
    if not encoded.rpartition("@")[0].isascii():
        return _utf8_address(mailbox.display_name, encoded)
    try:
        return Address(mailbox.display_name, addr_spec=encoded)
    except (ValueError, HeaderParseError) as error:
        raise RfcComplianceError(
            f'"{mailbox.address}" is not a valid email address: {error}.'
        ) from error


def _utf8_address(display_name: str, encoded: str) -> Address:
    """Read an address with a non-ASCII local part, which RFC 6532 allows.

    The engine's strict address reader refuses such a local part outright, so it is read as a
    header, where that is the one complaint tolerated.
    """
    header = _ADDRESS("To", encoded)
    complaints = [d for d in header.defects if not isinstance(d, NonASCIILocalPartDefect)]
    groups = _as_address_header(header).groups
    addresses = _as_address_header(header).addresses
    if complaints or len(groups) != 1 or len(addresses) != 1 or addresses[0].display_name:
        reason = complaints[0] if complaints else "not a single bare address"
        raise RfcComplianceError(f'"{encoded}" is not a valid email address: {reason}.')
    return Address(display_name, addresses[0].username, addresses[0].domain)


def _as_address_header(header: object) -> AddressHeader:
    """Name what the address registry builds: a header class that is an AddressHeader too.

    The stubs type every registry header as its base class alone.
    """
    return cast("AddressHeader", header)


def _parameters_of(header: object) -> Mapping[str, object]:
    """Read the decoded parameters of what the parameterized registries build.

    As :func:`_as_address_header` says, the stubs type the header as its base class alone.
    """
    return cast("ParameterizedMIMEHeader", header).params


def _finish(part: EnginePart, media_type: Parameterized, leaf: TextLeaf | BinaryLeaf) -> None:
    """Give a leaf the headers the engine's content setter does not write the way we need.

    Content-Type is replaced in place (the setter's own ``set_param`` would move it below
    Content-Transfer-Encoding) and the ``MIME-Version`` a setter may add is dropped.
    """
    part.replace_header("Content-Type", _make_header("Content-Type", media_type))
    if leaf.disposition is not None:
        add_header(part, "Content-Disposition", leaf.disposition)
    if leaf.content_id is not None:
        add_header(part, "Content-ID", MessageIds((leaf.content_id,)))
    del part["MIME-Version"]

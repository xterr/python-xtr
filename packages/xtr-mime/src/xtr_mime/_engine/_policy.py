"""The engine's policy and the header classes it builds fields with.

The policy checks every field as the generator writes it; the registries build each kind of
header the engine writes, and :class:`FoldedHeader` carries a field xtr-mime folded itself.
"""

from __future__ import annotations

from email.headerregistry import (
    AddressHeader,
    ContentDispositionHeader,
    ContentTypeHeader,
    DateHeader,
    HeaderRegistry,
    ParameterizedMIMEHeader,
    UnstructuredHeader,
)
from email.policy import EmailPolicy
from typing import TYPE_CHECKING, Final, TypeAlias, cast, final

from typing_extensions import override

from xtr_mime.exception import RfcComplianceError

from ._grammar import (
    FOLD_WIDTH,
    PACKAGE_FAILURES,
    SOURCE_FOLD,
    body_of,
    check_folded,
    check_name,
    refuse_forbidden,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from email._header_value_parser import UnstructuredTokenList
    from email.message import EmailMessage
    from typing import Self

    # The stubs make the policy generic in the message class it builds; the class is not.
    _EmailPolicy = EmailPolicy[EmailMessage]
else:
    _EmailPolicy = EmailPolicy

__all__ = [
    "ADDRESS",
    "CONTENT_TYPE",
    "DATE",
    "PARAMETERIZED",
    "POLICY",
    "UNSTRUCTURED",
    "UTF8_POLICY",
    "EnginePart",
    "FoldedHeader",
    "address_groups",
    "as_address_header",
    "check_addresses_kept",
    "parameters_of",
]


# Not final: its base declares the attributes its constructor sets, which a final class would
# be required to initialise itself.
class _WirePolicy(_EmailPolicy):
    """The engine's policy: every header field is checked as the generator writes it.

    The generator writes each field through :meth:`fold_binary` — with this policy, or with a
    clone of it that writes a ``multipart/signed`` subtree unfolded — so the check sees the
    bytes that reach the wire, whoever built the header.
    """

    @override
    def fold_binary(self, name: str, value: str) -> bytes:
        check_name(name)
        # A parsed part's header holds the bytes the parser read, undecoded: it is checked as
        # the text they are, its folds taken out, and written as read.
        is_parsed = not hasattr(value, "name")
        if is_parsed:
            refuse_forbidden(f"The {name} header", _parsed_text(name, value))
        try:
            written = super().fold_binary(name, value)
        except PACKAGE_FAILURES as error:
            raise RfcComplianceError(f"The {name} header cannot be written: {error}.") from error
        check_folded(written.decode("utf-8", "surrogateescape"))
        if is_parsed and name.lower() in _ADDRESS_HEADERS:
            check_addresses_kept(name, value, written.decode("ascii", "surrogateescape"))
        return written


POLICY: Final = _WirePolicy(
    linesep="\r\n", max_line_length=FOLD_WIDTH, mangle_from_=False, refold_source="none"
)
"""CRLF line ends and 76-column folding, what SMTP expects; a parsed header is written as read."""

UTF8_POLICY: Final = POLICY.clone(utf8=True)

# Quoted: the class is generic only in its type stubs, not at runtime. It is the parser's
# class too, so a parsed message and a built one are the same kind of value.
EnginePart: TypeAlias = "EmailMessage[str, str]"
"""A part or a whole message as the engine holds it; never seen outside xtr-mime."""


# Not final: the registry derives the class it builds from this one.
class _TextHeader(UnstructuredHeader):
    """Unstructured text whose words too long for a line stay plain.

    The package encodes such a word so that it can split it across lines. Marked as allowing
    no encoded word, it is written whole after a fold instead: RFC 5322 allows that line up to
    998 octets, and the check every field goes through refuses it beyond. A word that is not
    ASCII is still the package's to encode.
    """

    @staticmethod
    @override
    def value_parser(value: str) -> UnstructuredTokenList:
        tree = UnstructuredHeader.value_parser(value)
        for token in tree:
            # A terminal is one word or one run of whitespace, as the package folds them.
            if (
                isinstance(token, str)
                and len(token) >= FOLD_WIDTH
                and token.isascii()
                and not token.isspace()
            ):
                token.as_ew_allowed = False
        return tree


UNSTRUCTURED: Final = HeaderRegistry(default_class=_TextHeader, use_default_map=False)
DATE: Final = HeaderRegistry(default_class=DateHeader, use_default_map=False)
ADDRESS: Final = HeaderRegistry(default_class=AddressHeader, use_default_map=False)
# The stubs give these two a class-level `max_count` the registry's parameter type rejects;
# at runtime the registry takes any header class, so they are passed as the type it names.
CONTENT_TYPE: Final = HeaderRegistry(
    default_class=cast("type[UnstructuredHeader]", ContentTypeHeader), use_default_map=False
)
PARAMETERIZED: Final = HeaderRegistry(
    default_class=cast("type[UnstructuredHeader]", ContentDispositionHeader),
    use_default_map=False,
)
# The headers the package reads as addresses.
_ADDRESS_HEADERS: Final = frozenset(
    name for name, kind in HeaderRegistry().registry.items() if issubclass(kind, AddressHeader)
)


@final
class FoldedHeader(str):  # noqa: SLOT000 -- a str subclass cannot have non-empty __slots__
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


def _parsed_text(name: str, value: str) -> str:
    """Read a parsed header's undecoded bytes as the UTF-8 text they are, unfolded."""
    try:
        text = value.encode("utf-8", "surrogateescape").decode("utf-8", "surrogateescape")
    except UnicodeError as error:
        raise RfcComplianceError(f"The {name} header is not text: {error}.") from error
    return SOURCE_FOLD.sub("", text)


def check_addresses_kept(name: str, source: str, written: str) -> None:
    """Refuse a parsed address header written as other addresses than the ones it holds."""
    if address_groups(name, source) != address_groups(name, body_of(name, written)):
        raise RfcComplianceError(
            f"The {name} header would not read back to the addresses it holds: {written!r}."
        )


def address_groups(name: str, body: str) -> list[tuple[bool, tuple[str, ...]]]:
    """Read ``body`` as the engine does: each item a group or not, and its addresses."""
    read = as_address_header(ADDRESS(name, SOURCE_FOLD.sub("", body)))
    return [
        (group.display_name is not None, tuple(a.addr_spec for a in group.addresses))
        for group in read.groups
    ]


def as_address_header(header: object) -> AddressHeader:
    """Name what the address registry builds: a header class that is an AddressHeader too.

    The stubs type every registry header as its base class alone.
    """
    return cast("AddressHeader", header)


def parameters_of(header: object) -> Mapping[str, object]:
    """Read the decoded parameters of what the parameterized registries build.

    As :func:`as_address_header` says, the stubs type the header as its base class alone.
    """
    return cast("ParameterizedMIMEHeader", header).params

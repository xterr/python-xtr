"""An email address with the name shown next to it."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final, final

import idna
from email_validator import EmailNotValidError, validate_email
from typing_extensions import override

from ._engine import Mailbox, encode_idn_address, header_body
from .exception import InvalidArgumentError, RfcComplianceError

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["Address"]

_TRIMMED: Final = " \t\n\r\0\x0b"
_NAME_CONTROL_CHARACTERS: Final = re.compile(r"[\x00-\x08\x0a-\x1f\x7f]")
_ADDRESS_CONTROL_CHARACTERS: Final = re.compile(r"[\x00-\x1f\x7f]")

# `Name <address>`: everything between the first "<" and the last ">" is the address, so a
# quoted local part may hold angle brackets; whatever follows the last ">" is dropped.
_FROM_STRING: Final = re.compile(r"(?P<display_name>[^<]*)<(?P<address>.*)>[^>]*")

# Most addresses are dot-atoms of letters, digits, "_", "+" and "-" on a plain host name; this
# settles them without the full grammar, which is the main cost of building a simple email.
_SIMPLE_ADDRESS: Final = re.compile(
    r"(?=[^@]{1,64}@[^@]{1,63}\Z)[a-zA-Z0-9_+-]++(?:\.[a-zA-Z0-9_+-]++)*+"
    r"@(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,28}[a-zA-Z0-9])?\.)++[a-zA-Z](?:[a-zA-Z0-9-]{0,28}[a-zA-Z0-9])?"
)

# A quoted local part may hold "@", so the split is after its closing quote; an unquoted one
# cannot, so it ends at the first "@".
_QUOTED_LOCAL_PART: Final = re.compile(r'(?P<local>"(?:[^"\\]|\\.)*")@(?P<domain>.*)', re.DOTALL)
_LOCAL_PART: Final = re.compile(r"(?P<local>[^@]*)@(?P<domain>.*)", re.DOTALL)

# Printable ASCII but "[", "]" and "\" between brackets, optionally followed by a comment.
_DOMAIN_LITERAL: Final = re.compile(r"\[[!-Z^-~]+\](?: *\([^()\\]*\))?")

# The validator judges the local part against a neutral domain: it refuses names reserved for
# special use (localhost, .local, .invalid, ...), which are valid in an address and do receive
# mail on a private network, so the domain is checked here instead.
_NEUTRAL_DOMAIN: Final = "example.com"

# The display name is rendered next to a stand-in address, then cut off it: the engine writes
# a name only as part of an address, and the real address may be one it refuses to write.
_STAND_IN: Final = "stand-in@example.com"


@final
class Address:
    """An email address and the display name shown next to it.

    The address is checked against the mail grammar, international (RFC 6532) addresses
    included, but not against what an SMTP session accepts — the local part is not limited to
    64 octets, for one: that is the envelope's and the transport's call. No DNS query is made.

    Two addresses are equal when both the address and the name are: an address is a value,
    and a recipient list is compared and de-duplicated by value.
    """

    __slots__ = ("_address", "_name")

    def __init__(self, address: str, name: str = "") -> None:
        """Check ``address`` and keep it and ``name``, both trimmed.

        Control characters are removed from the name (a tab, the one a phrase allows, stays);
        in the address they are refused, since one could start a new header line.

        Raises:
            InvalidArgumentError: The address contains a control character.
            RfcComplianceError: The address is not a valid email address.
        """
        self._address = address.strip(_TRIMMED)
        self._name = _NAME_CONTROL_CHARACTERS.sub("", name).strip(_TRIMMED)
        if _ADDRESS_CONTROL_CHARACTERS.search(self._address):
            raise InvalidArgumentError("Email address contains control characters.")
        if not _is_valid(self._address):
            raise RfcComplianceError(
                f'Email "{address}" does not comply with addr-spec of RFC 5322.'
            )

    @classmethod
    def create(cls, address: Address | str) -> Address:
        """Return ``address`` if it is one, else parse it from ``address`` or ``Name <address>``.

        Quotes and spaces around the name are dropped, so a name may be written ``"Name"``
        or ``'Name'``.

        Raises:
            InvalidArgumentError: A ``<`` is there but no ``Name <address>`` can be read.
            RfcComplianceError: The address read is not a valid email address.
            TypeError: ``address`` is neither an :class:`Address` nor a string.
        """
        if isinstance(address, Address):
            return address
        if "<" not in address:
            return cls(address)
        match = _FROM_STRING.search(address)
        if match is None:
            raise InvalidArgumentError(
                f'Could not parse "{address}" to an "xtr_mime.Address" instance.'
            )
        return cls(match["address"], match["display_name"].strip(" '\""))

    @classmethod
    def create_array(cls, addresses: Iterable[Address | str]) -> list[Address]:
        """Apply :meth:`create` to every item, in order."""
        return [cls.create(address) for address in addresses]

    def get_address(self) -> str:
        """Return the address as given (trimmed): an international domain stays in Unicode."""
        return self._address

    def get_name(self) -> str:
        """Return the display name, empty when there is none."""
        return self._name

    def get_encoded_address(self) -> str:
        """Return the address with its domain written in ASCII (punycode) when it is not already.

        The local part is left as it is: a non-ASCII one cannot be encoded, it needs an SMTPUTF8
        session (see :meth:`has_unicode_localpart`). The domain was checked when the address
        was built, so it always encodes; there is no silently emptied domain.
        """
        return encode_idn_address(self._address)

    def get_encoded_name(self) -> str:
        """Return the display name as it is written in a header, empty when there is none.

        Quoted when it holds a special character, as encoded words when it is not ASCII — the
        engine's choice, on one line.

        Raises:
            RfcComplianceError: The name holds an encoded word, which a reader would show
                decoded rather than as the text it is.
        """
        if not self._name:
            return ""
        rendered = _unfold(header_body("To", [Mailbox(self._name, _STAND_IN)]))
        return rendered.removesuffix(f" <{_STAND_IN}>")

    def to_string(self) -> str:
        """Return the address as written in a header: ``name <address>``, or the address alone.

        Rendered by the engine, on one line, the domain in ASCII. An address with a non-ASCII
        local part is written in raw UTF-8 (RFC 6532), its name included — the form an SMTPUTF8
        session carries; without SMTPUTF8 such an address cannot be sent at all.

        Raises:
            RfcComplianceError: The name holds an encoded word, which a reader would show
                decoded rather than as the text it is.
        """
        return _unfold(header_body("To", [Mailbox(self._name, self._address)]))

    def has_unicode_localpart(self) -> bool:
        """Tell whether the local part holds a non-ASCII character.

        Such an address can only be sent through a server that speaks SMTPUTF8 (RFC 6531),
        whereas a non-ASCII domain alone is written in punycode and needs nothing special.
        """
        return not self._address.rpartition("@")[0].isascii()

    @override
    def __str__(self) -> str:
        """Return :meth:`to_string`."""
        return self.to_string()

    @override
    def __repr__(self) -> str:
        """Show the address and the name as given."""
        return f"Address({self._address!r}, {self._name!r})"

    @override
    def __eq__(self, other: object) -> bool:
        """Compare the address and the name."""
        if not isinstance(other, Address):
            return NotImplemented
        return (self._address, self._name) == (other._address, other._name)

    @override
    def __hash__(self) -> int:
        """Hash the address and the name, as :meth:`__eq__` compares them."""
        return hash((self._address, self._name))


def _is_valid(address: str) -> bool:
    if _SIMPLE_ADDRESS.fullmatch(address):
        return True
    parts = _QUOTED_LOCAL_PART.fullmatch(address) or _LOCAL_PART.fullmatch(address)
    if parts is None:
        return False
    return _is_valid_local_part(parts["local"]) and _is_valid_domain(parts["domain"])


def _is_valid_local_part(local: str) -> bool:
    try:
        _ = validate_email(
            f"{local}@{_NEUTRAL_DOMAIN}",
            check_deliverability=False,
            allow_smtputf8=True,
            allow_quoted_local=True,
            allow_domain_literal=True,
            globally_deliverable=False,
        )
    except EmailNotValidError:
        return False
    return True


def _is_valid_domain(domain: str) -> bool:
    if domain.startswith("["):
        return _DOMAIN_LITERAL.fullmatch(domain) is not None
    # The IDNA codec accepts a final dot (the DNS root); an address does not.
    if domain.endswith("."):
        return False
    try:
        _ = idna.encode(domain, uts46=True, std3_rules=True)
    except idna.IDNAError:
        return False
    return True


def _unfold(rendered: str) -> str:
    """Join folded lines: a fold is a line break before a space, and the space stays."""
    return rendered.replace("\r\n", "")

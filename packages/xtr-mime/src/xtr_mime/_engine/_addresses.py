"""Addresses as the engine writes them: punycoded domains, literal names, RFC 6532 local parts."""

from __future__ import annotations

import re
from email.errors import HeaderParseError, NonASCIILocalPartDefect
from email.headerregistry import Address, Group
from typing import Final

import idna

from xtr_mime._error_text import capped
from xtr_mime.exception import RfcComplianceError

from ._grammar import refuse_forbidden
from ._policy import ADDRESS, as_address_header
from ._values import Mailbox, MailboxGroup

__all__ = ["encode_idn_address", "to_address", "to_engine_address"]

# What the engine's readers take for an encoded word, which they decode instead of showing.
_ENCODED_WORD: Final = re.compile(r"=\?.*\?=", re.DOTALL)


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
            f'The domain "{capped(domain)}" of "{capped(address)}" cannot be written in ASCII: '
            f"{error}."
        ) from error
    return f"{local}@{encoded}"


def _check_literal_name(display_name: str) -> None:
    """Refuse a name the engine would decode rather than write as the text it is.

    The engine reads an encoded word in a name as one and writes the decoded text, unquoted —
    where it can read as an address (or, in a group name, crash the engine's folder).
    """
    refuse_forbidden("A display name", display_name)
    if _ENCODED_WORD.search(display_name):
        raise RfcComplianceError(
            f'The display name "{capped(display_name)}" holds an encoded word: a reader would '
            "show it decoded, not as the literal text it is."
        )


def to_engine_address(item: Mailbox | MailboxGroup) -> Address | Group:
    match item:
        case Mailbox():
            return to_address(item)
        case MailboxGroup():
            _check_literal_name(item.display_name)
            return Group(item.display_name, [to_address(member) for member in item.mailboxes])


def to_address(mailbox: Mailbox) -> Address:
    _check_literal_name(mailbox.display_name)
    refuse_forbidden("An email address", mailbox.address)
    if "=?" in mailbox.address:
        raise RfcComplianceError(
            f'"{capped(mailbox.address)}" holds an encoded word: the engine would decode it into '
            "another address."
        )
    encoded = encode_idn_address(mailbox.address)
    if not encoded.rpartition("@")[0].isascii():
        return _utf8_address(mailbox.display_name, encoded)
    try:
        return Address(mailbox.display_name, addr_spec=encoded)
    except (ValueError, HeaderParseError) as error:
        raise RfcComplianceError(
            f'"{capped(mailbox.address)}" is not a valid email address: {error}.'
        ) from error


def _utf8_address(display_name: str, encoded: str) -> Address:
    """Read an address with a non-ASCII local part, which RFC 6532 allows.

    The engine's strict address reader refuses such a local part outright, so it is read as a
    header, where that is the one complaint tolerated.
    """
    header = ADDRESS("To", encoded)
    complaints = [d for d in header.defects if not isinstance(d, NonASCIILocalPartDefect)]
    groups = as_address_header(header).groups
    addresses = as_address_header(header).addresses
    if complaints or len(groups) != 1 or len(addresses) != 1 or addresses[0].display_name:
        reason = complaints[0] if complaints else "not a single bare address"
        raise RfcComplianceError(f'"{capped(encoded)}" is not a valid email address: {reason}.')
    return Address(display_name, addresses[0].username, addresses[0].domain)

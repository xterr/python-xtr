"""Read a rendered address back as a mail client does, decoded.

Which encoded-word form the engine picks is its business, not the address class's, so the
address tests compare what a reader gets back.
"""

from __future__ import annotations

from email import policy as stdlib_policy
from email.headerregistry import AddressHeader, BaseHeader
from typing import cast

__all__ = ["UNSAFE_IN_A_MESSAGE", "read_address", "read_name"]

# What a log line must never carry: a line break, a line separator, a lone surrogate.
UNSAFE_IN_A_MESSAGE = ("\r", "\n", "\x85", "\u2028", "\u2029", "\ud800", "\udc80")


def read_address(rendered: str) -> tuple[str, str]:
    """Read a rendered address back into its decoded display name and its address."""
    header = cast("BaseHeader", stdlib_policy.default.header_factory("To", rendered))
    assert isinstance(header, AddressHeader)
    (mailbox,) = header.addresses
    return mailbox.display_name, f"{mailbox.username}@{mailbox.domain}"


def read_name(encoded_name: str) -> str:
    return read_address(f"{encoded_name} <someone@example.com>")[0]

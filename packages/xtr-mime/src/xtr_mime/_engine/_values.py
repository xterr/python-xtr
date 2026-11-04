"""The typed values the rest of xtr-mime hands the engine: header values and leaf parts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, TypeAlias, final

__all__ = [
    "BinaryLeaf",
    "HeaderValue",
    "Mailbox",
    "MailboxGroup",
    "MessageIds",
    "Parameterized",
    "Path",
    "TextLeaf",
    "TransferEncoding",
]

TransferEncoding: TypeAlias = Literal["7bit", "8bit", "quoted-printable", "base64"]


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
    ``content_id`` is the bare identifier, written ``<content_id>``. In ``8bit`` and
    ``binary`` the line breaks are written as CRLF, the only line end SMTP carries.
    """

    content: bytes
    maintype: str
    subtype: str
    transfer_encoding: TransferEncoding | Literal["binary"]
    parameters: Mapping[str, str] = field(default_factory=dict[str, str])
    disposition: Parameterized | None = None
    content_id: str | None = None

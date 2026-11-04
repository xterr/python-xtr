"""The grammar every header the engine writes is held to, and the checks that enforce it.

Whoever builds a field — a typed value, a parsed part, a field written by hand — it goes
through these checks before it reaches the wire.
"""

from __future__ import annotations

import re
from email.errors import MessageError
from typing import Final

from xtr_mime._error_text import capped
from xtr_mime.exception import RfcComplianceError

__all__ = [
    "FOLD_WIDTH",
    "PACKAGE_FAILURES",
    "SOURCE_FOLD",
    "TOKEN",
    "body_of",
    "check_boundary",
    "check_folded",
    "check_message_id",
    "check_name",
    "check_token",
    "join_blank_lines",
    "refuse_forbidden",
]

FOLD_WIDTH: Final = 76
# RFC 5322, 2.1.1: the hard limit on a line, whatever folding allows.
_MAX_LINE_LENGTH: Final = 998

# Every C0 control but TAB, DEL, the C1 controls (NEL among them), the line and paragraph
# separators and a lone surrogate: a line break would start a new header, some readers end a
# line at any of the others, and a lone surrogate is a byte that was never text.
_FORBIDDEN: Final = re.compile(r"[\x00-\x08\x0a-\x1f\x7f-\x9f\u2028\u2029\ud800-\udfff]")
# RFC 5322, 2.2: printable ASCII but the colon, which ends the name.
_FIELD_NAME: Final = re.compile(r"[!-9;-~]+")
# RFC 2045, 5.1: printable ASCII but space and the tspecials.
TOKEN: Final = re.compile(r"[!#$%&'*+\-.^_`{|}~0-9A-Za-z]+")
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
# A fold in a header as the parser keeps it, from a source with CRLF or bare LF line ends.
SOURCE_FOLD: Final = re.compile(r"\r?\n(?=[ \t])")

# What the package raises on a value it cannot handle, rather than an error of its own.
PACKAGE_FAILURES: Final = (
    AttributeError,
    LookupError,
    RecursionError,
    TypeError,
    ValueError,
    MessageError,
)


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
            f'"{capped(identifier)}" is not a message identifier: id-left@id-right (RFC 5322, '
            "3.6.4), without spaces, angle brackets or quoted pairs."
        )


def check_name(name: str) -> None:
    if not _FIELD_NAME.fullmatch(name):
        raise RfcComplianceError(
            f'"{capped(name)}" is not a header name: printable ASCII, without a space or a colon '
            "— a reader ends the name at its first colon."
        )


def check_boundary(boundary: str) -> None:
    # "=?" opens an encoded word: the engine would take such a boundary for one and replace it.
    if not _BOUNDARY.fullmatch(boundary) or "=?" in boundary:
        raise RfcComplianceError(
            f'The boundary "{capped(boundary)}" is not 1 to 70 RFC 2046 boundary characters '
            'ending in one that is not a space, without "=?".'
        )


def check_token(what: str, token: str) -> None:
    if not TOKEN.fullmatch(token):
        raise RfcComplianceError(f'The {what} "{capped(token)}" is not a token.')


def body_of(name: str, folded: str) -> str:
    return folded[len(name) + 1 :].removesuffix("\r\n")


def join_blank_lines(folded: str) -> str:
    """Keep every run of whitespace the engine folds on a line that holds more than it.

    The package folds a run of whitespace too long to share a line onto a line of its own,
    which RFC 5322 forbids writing. Taking out the line break after such a line — or before
    it, when it is the last — moves the run onto its neighbour: unfolding takes out every line
    break the same way, so the field still reads as the text it was.
    """
    lines = folded.removesuffix("\r\n").split("\r\n")
    if not folded.endswith("\r\n") or all(line.strip(" \t") for line in lines[1:]):
        return folded
    joined = [lines[0]]
    held = ""
    for line in lines[1:]:
        if line.strip(" \t"):
            joined.append(held + line)
            held = ""
        else:
            held += line
    joined[-1] += held
    return "\r\n".join(joined) + "\r\n"


def refuse_forbidden(what: str, value: str) -> None:
    found = _FORBIDDEN.search(value)
    if found:
        raise RfcComplianceError(
            f"{what} must not contain a control character, a line separator or a lone "
            f'surrogate: {found.group()!r} in "{capped(value)}".'
        )


def check_folded(folded: str) -> None:
    """Refuse a folded field any line of which would start a header of its own, or break one.

    Run on everything the engine folds, so a line break that slips through it — as one did
    before CVE-2024-6923 was fixed — never reaches the wire, nor a character some reader ends
    a line at, nor a line longer than RFC 5322 allows, nor a continuation line of whitespace
    alone, which RFC 5322 forbids writing and a lenient reader takes for the end of the headers.
    """
    lines = folded.removesuffix("\r\n").split("\r\n")
    if (
        not folded.endswith("\r\n")
        or any("\r" in line or "\n" in line for line in lines)
        or not all(line.startswith((" ", "\t")) and line.strip(" \t") for line in lines[1:])
    ):
        raise RfcComplianceError(
            f'A folded header has a line that is not a continuation of it: "{capped(folded)}".'
        )
    for line in lines:
        refuse_forbidden("A folded header", line)
        if len(line.encode("utf-8", "surrogateescape")) > _MAX_LINE_LENGTH:
            # The value is not quoted: the line is too long to show, and it is the value.
            raise RfcComplianceError(
                f"The {lines[0].partition(':')[0]} header has a line longer than "
                f"{_MAX_LINE_LENGTH} octets."
            )

"""Read a rendered part back the way a mail client does.

A part's body bytes are the engine's — a text body ends with a line break, a base64 body is cut
into lines — so a test compares what a reader decodes, not the bytes, where those differ.
"""

from __future__ import annotations

from email import policy
from email.parser import BytesParser
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from email.message import EmailMessage

    from xtr_mime.part import AbstractPart

__all__ = ["decoded_body", "read_part"]


def read_part(part: AbstractPart) -> EmailMessage:
    """Parse what ``part`` renders."""
    return BytesParser(policy=policy.default).parsebytes(b"".join(part.to_iterable()))


def decoded_body(part: AbstractPart) -> bytes:
    """Return the body of a leaf part with its transfer encoding undone."""
    return cast("bytes", read_part(part).get_payload(decode=True))

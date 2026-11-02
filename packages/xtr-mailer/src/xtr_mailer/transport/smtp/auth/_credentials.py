"""Credentials written the way an ``AUTH`` exchange carries them."""

from __future__ import annotations

import base64

from xtr_mailer.exception import InvalidArgumentError

__all__ = ["base64_line", "utf8"]


def utf8(text: str) -> bytes:
    """Return ``text`` in UTF-8, the bytes a credential is sent as.

    Raises:
        InvalidArgumentError: ``text`` holds a character UTF-8 cannot write. The message
            does not quote it: it is part of a credential.
    """
    try:
        return text.encode()
    except UnicodeEncodeError:
        raise InvalidArgumentError(
            "The SMTP credentials must only hold characters UTF-8 can write."
        ) from None


def base64_line(text: str) -> str:
    """Return ``text`` in UTF-8, base64-encoded, as one line of the exchange."""
    return base64.b64encode(utf8(text)).decode("ascii")

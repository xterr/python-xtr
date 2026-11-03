"""SMTP replies written back as the server sent them, and the error a refused one raises."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

from xtr_mailer._error_text import shown
from xtr_mailer.exception import UnexpectedResponseError

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["message_id_of", "render_reply", "unexpected_response"]

#: The characters of a reply an error shows; the error's debug keeps the whole of it.
_SHOWN_CHARACTERS: Final = 1000
_SURROGATE: Final = re.compile("[\ud800-\udfff]")
_MESSAGE_ID: Final = re.compile(
    r"^250 (?:\S+ )?Ok:?+ (?:queued as |id=)?+(?P<id>[A-Z0-9._-]++)", re.IGNORECASE | re.MULTILINE
)


def message_id_of(reply: str) -> str:
    """Return the id a server's acceptance of an email names, ``""`` when it names none."""
    found = _MESSAGE_ID.search(reply)
    return found["id"] if found else ""


def render_reply(code: int, text: str) -> str:
    """Rebuild a reply from its code and its lines, joined by CRLF.

    A reply that could not be parsed has no code (``0`` or less); ``text`` is then
    what the server sent, and is returned trimmed. Bytes that were not UTF-8 come back
    as U+FFFD, so the reply can be written anywhere text goes.
    """
    text = _SURROGATE.sub("\ufffd", text)
    if code <= 0:
        return text.strip()
    lines = text.split("\n")
    rendered = [f"{code}-{line}" for line in lines[:-1]]
    rendered.append(f"{code} {lines[-1]}")
    return "\r\n".join(rendered).strip()


def unexpected_response(
    expected_codes: Sequence[int], code: int, reply: str
) -> UnexpectedResponseError:
    """Build the error for ``reply``, whose ``code`` is none of ``expected_codes``.

    A reply with no code reads as an "empty code" and carries code ``0``. The reply is the
    server's to write: it is shown escaped — its line breaks and the control characters that
    would steer a terminal the error is printed on — and cut short.
    """
    got = f'code "{code}"' if code > 0 else "empty code"
    with_message = f', with message "{shown(reply, _SHOWN_CHARACTERS)}"' if reply else ""
    expected = "/".join(str(expected_code) for expected_code in expected_codes)
    return UnexpectedResponseError(
        f'Expected response code "{expected}" but got {got}{with_message}.', max(code, 0)
    )

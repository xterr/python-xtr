"""Cleans a display name — an address's or a group's — into the text a header shows.

Control characters are dropped (a tab, the one a phrase allows, stays) and the name trimmed.
A lone surrogate is refused: decoded with ``surrogateescape``, a byte that is not UTF-8
survives as a surrogate code point with no partner. It is not text, and the email package of
some Python versions cannot even write one in a quoted name.
"""

from __future__ import annotations

import re
from typing import Final

from .exception import RfcComplianceError

__all__ = ["TRIMMED", "clean_display_name"]

TRIMMED: Final = " \t\n\r\0\x0b"
"""What is trimmed off a name, and off an address."""

_CONTROL_CHARACTERS: Final = re.compile(r"[\x00-\x08\x0a-\x1f\x7f]")
# In a str every surrogate is alone: a character outside the BMP is one code point there.
_LONE_SURROGATE: Final = re.compile(r"[\ud800-\udfff]")


def clean_display_name(name: str, what: str) -> str:
    """Return ``name`` without its control characters, trimmed; ``what`` names it in errors.

    Raises:
        RfcComplianceError: ``name`` holds a lone surrogate.
    """
    cleaned = _CONTROL_CHARACTERS.sub("", name).strip(TRIMMED)
    if _LONE_SURROGATE.search(cleaned):
        raise RfcComplianceError(
            f"{what} {name!r} holds a lone surrogate, left by a byte that did not decode; a "
            "name must be text."
        )
    return cleaned

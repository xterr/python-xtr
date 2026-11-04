"""What the S/MIME encrypting listener does for a recipient without a certificate.

The listener and the bundle's configuration both check a mode with :func:`checked_mode`.
"""

from __future__ import annotations

from typing import Final

from ._error_text import shown
from .exception import InvalidArgumentError

__all__ = ["ENCRYPT", "FAIL", "MODES", "SKIP", "checked_mode"]

FAIL: Final = "fail"
ENCRYPT: Final = "encrypt"
SKIP: Final = "skip"
MODES: Final = frozenset({FAIL, ENCRYPT, SKIP})


def checked_mode(mode: object) -> str:
    """Return ``mode`` when it is one of the modes.

    Raises:
        InvalidArgumentError: ``mode`` is not one of the modes, or not a string at all.
    """
    if isinstance(mode, str) and mode in MODES:
        return mode
    got = (
        f'"{shown(mode)}"' if isinstance(mode, str) else f'a value of type "{type(mode).__name__}"'
    )
    raise InvalidArgumentError(
        f'The "on_missing_certificate" option must be "fail", "encrypt" or "skip" (got {got}).'
    )

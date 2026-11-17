"""Makes the one-time values a page's own scripts and styles are allowed by."""

from __future__ import annotations

import secrets
from typing import Final, final

__all__ = ["NonceGenerator"]

_BYTES: Final = 16


@final
class NonceGenerator:
    """Returns a fresh nonce on every call: 128 random bits, as 32 hexadecimal characters."""

    __slots__ = ()

    def generate(self) -> str:
        """Return a fresh nonce."""
        return secrets.token_hex(_BYTES)

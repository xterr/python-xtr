"""Which header values the profiler panel never keeps: those carrying a credential."""

from __future__ import annotations

from typing import Final

__all__ = ["MASK", "masked_header"]

MASK: Final = "******"

_SENSITIVE_HEADERS: Final = frozenset(
    {"authorization", "proxy-authorization", "cookie", "set-cookie", "x-api-key"}
)
_SENSITIVE_WORDS: Final = ("password", "secret", "token", "passwd", "api_key", "apikey")


def masked_header(name: str, value: str) -> str:
    """Return ``value``, or the mask when a header named ``name`` likely carries a credential.

    A profile is written to disk and shown in a browser, so a credential an application put
    in a header — a provider's key, a signed token — must not be kept in it.
    """
    lowered = name.lower()
    if lowered in _SENSITIVE_HEADERS or any(word in lowered for word in _SENSITIVE_WORDS):
        return MASK
    return value

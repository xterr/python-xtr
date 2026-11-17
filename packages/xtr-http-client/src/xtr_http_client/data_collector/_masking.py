"""Credentials, kept out of what a profile stores about a request."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final, cast

__all__ = ["MASK", "masked", "masked_header_line", "sensitive_field", "sensitive_header"]

MASK: Final = "******"
"""What a credential is kept as."""

_HEADERS: Final = frozenset(
    {"authorization", "proxy-authorization", "cookie", "set-cookie", "x-api-key"}
)
_FIELD_WORDS: Final = ("password", "secret", "token", "passwd", "api_key", "apikey")


def sensitive_field(name: str) -> bool:
    """Tell whether a field called ``name`` is named like a credential."""
    lowered = name.lower()
    return any(word in lowered for word in _FIELD_WORDS)


def sensitive_header(name: str) -> bool:
    """Tell whether a header called ``name`` carries a credential."""
    return name.lower() in _HEADERS or sensitive_field(name)


def masked_header_line(line: str) -> str:
    """Return a ``Name: value`` line with the value masked when the header is a credential.

    A status line has no colon after a header name, so it is kept as it is.
    """
    name, colon, _ = line.partition(":")
    if colon and sensitive_header(name.strip()):
        return f"{name}: {MASK}"
    return line


def masked(value: object) -> object:
    """Return ``value`` with every entry named like a credential masked, however deep."""
    if isinstance(value, Mapping):
        entries = cast("Mapping[object, object]", value)
        return {
            key: MASK if isinstance(key, str) and sensitive_field(key) else masked(item)
            for key, item in entries.items()
        }
    if isinstance(value, list | tuple):
        return [masked(item) for item in cast("list[object] | tuple[object, ...]", value)]
    return value

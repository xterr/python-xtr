"""Puts what was given into an error message without letting it break the message.

An error ends up in a log: a line break, a null byte or a lone surrogate taken from what was
given must not reach it as such, so each is shown escaped, as ``repr`` shows it — and a long
value is cut short, so an error repeats enough to find it, never a whole header's worth.
"""

from __future__ import annotations

from typing import Final

__all__ = ["shown"]

_SHOWN_LENGTH: Final = 64


def shown(value: str) -> str:
    """Show the start of ``value`` as ``repr`` does, without its quotes, ``…`` if it goes on."""
    return repr(value[:_SHOWN_LENGTH])[1:-1] + ("…" if len(value) > _SHOWN_LENGTH else "")

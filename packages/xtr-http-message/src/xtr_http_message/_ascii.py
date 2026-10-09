"""Lowercasing that stops where the grammars this package reads stop: at ASCII."""

from __future__ import annotations

from typing import Final

__all__ = ["lower"]

# `str.lower` is the wrong tool twice over. It recases letters outside ASCII,
# and a non-ASCII host is not ours to touch; and it folds characters such as
# the Kelvin sign onto an ASCII letter, which would make a header name match
# one it does not equal.
_LOWERCASE: Final = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")


def lower(text: str) -> str:
    """Return ``text`` with its ASCII letters lowercased and every other character as it was.

    Args:
        text: The text to lowercase.

    Returns:
        The text, with ``A``-``Z`` mapped onto ``a``-``z`` and nothing else
        touched.
    """
    return text.translate(_LOWERCASE)

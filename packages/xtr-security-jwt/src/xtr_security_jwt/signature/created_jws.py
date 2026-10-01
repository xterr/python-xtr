"""A token just built, and whether it carries a signature."""

from __future__ import annotations

from typing import final

__all__ = ["CreatedJws"]


@final
class CreatedJws:
    """The compact token a provider produced, and whether it was signed.

    An immutable value: a provider hands one back from ``create`` so the encoder
    can refuse a token that came back unsigned before it is ever returned to a
    caller.

    Attributes:
        token: The compact serialized token.
        is_signed: Whether the token carries a signature.
    """

    __slots__ = ("_is_signed", "_token")

    def __init__(self, token: str, *, is_signed: bool) -> None:
        """Record the ``token`` and whether it ``is_signed``."""
        self._token = token
        self._is_signed = is_signed

    def is_signed(self) -> bool:
        """Tell whether the token carries a signature."""
        return self._is_signed

    def get_token(self) -> str:
        """Return the compact serialized token."""
        return self._token

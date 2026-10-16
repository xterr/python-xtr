"""The one surface every token generator answers."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["TokenGeneratorInterface"]


@runtime_checkable
class TokenGeneratorInterface(Protocol):
    """Mints the value a token id is answered with.

    Synchronous, and kept that way: minting is pure randomness, it reaches
    nothing — the storage is what a caller waits on.
    """

    def generate_token(self) -> str:
        """Return a fresh value, never seen before."""
        ...

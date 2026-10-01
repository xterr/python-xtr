"""What can hand out the public half of the key material as text."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["KeyDumperInterface"]


@runtime_checkable
class KeyDumperInterface(Protocol):
    """Produces the public key text, deriving it from the private key when needed.

    A key loader that can also publish its verifying key implements this, so the
    public key can be handed out even when only a private key was configured.
    """

    def dump_key(self) -> str:
        """Return the public key text, derived from the private key when unset."""
        ...

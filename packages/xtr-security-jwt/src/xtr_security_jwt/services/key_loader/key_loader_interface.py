"""What hands a JWS provider the key material it signs and verifies with."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["KeyLoaderInterface"]

#: The kind of key a caller asks :meth:`KeyLoaderInterface.load_key` for.
TYPE_PUBLIC: Final[str] = "public"

#: The kind of key a caller asks :meth:`KeyLoaderInterface.load_key` for.
TYPE_PRIVATE: Final[str] = "private"


@runtime_checkable
class KeyLoaderInterface(Protocol):
    """Reads the signing and verifying key material out of where it is kept.

    A loader knows where the keys live — a raw string, a file path — and hands
    them out as text. A provider turns that text into keys; the loader itself
    makes no cryptographic decision. A caller names the kind of key with the
    module constants :data:`TYPE_PUBLIC` and :data:`TYPE_PRIVATE`.
    """

    def load_key(self, key_type: str) -> str:
        """Return the key of ``key_type`` — :data:`TYPE_PUBLIC` or :data:`TYPE_PRIVATE`."""
        ...

    def get_passphrase(self) -> str | None:
        """Return the pass phrase the private key is encrypted with, if any."""
        ...

    def get_signing_key(self) -> str | None:
        """Return the private key text, or ``None`` when this loader only verifies."""
        ...

    def get_public_key(self) -> str | None:
        """Return the public key text, or ``None`` when it is derived from the private key."""
        ...

    def get_additional_public_keys(self) -> Sequence[str]:
        """Return the extra public keys a token may also be verified against."""
        ...

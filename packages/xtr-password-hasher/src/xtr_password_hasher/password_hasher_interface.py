"""What every password hasher answers to."""

from __future__ import annotations

from typing import Final, Protocol, runtime_checkable

__all__ = ["MAX_PASSWORD_LENGTH", "PasswordHasherInterface"]

MAX_PASSWORD_LENGTH: Final = 4096
"""The greatest input length, in UTF-8 bytes, any hasher processes.

A longer input is refused by :meth:`PasswordHasherInterface.hash` — an
unbounded input would let a caller spend a hasher's whole cost on one call —
and rejected by :meth:`PasswordHasherInterface.verify` as a non-match. The
bound is on the encoded byte length, since that is the work a hasher reads: a
multi-byte character costs its bytes. It is a denial-of-service guard, not a
rule on how long a password may be.
"""


@runtime_checkable
class PasswordHasherInterface(Protocol):
    """Turns a plaintext password into a hash, and checks one against it.

    A hash is opaque: it names its own algorithm and parameters, so the same
    hasher — or one built from a later, stronger configuration — reads them
    back to verify and to decide whether the hash should be replaced.
    """

    def hash(self, plain: str) -> str:
        """Hash ``plain`` and return the self-describing hash to store.

        Args:
            plain: The plaintext password.

        Raises:
            InvalidPasswordError: When ``plain`` is longer than
                :data:`MAX_PASSWORD_LENGTH`.
        """
        ...

    def verify(self, hashed: str, plain: str) -> bool:
        """Return whether ``plain`` is the password ``hashed`` was made from.

        Never raises for an over-long ``plain``: it cannot match a hash of a
        bounded input, so the answer is ``False``. The comparison is
        constant-time.
        """
        ...

    def needs_rehash(self, hashed: str) -> bool:
        """Return whether ``hashed`` should be replaced by a fresh hash.

        True when ``hashed`` was made by a weaker algorithm or with weaker
        parameters than this hasher now uses — the moment to rehash the
        plaintext, which is only in hand right after a successful verify.
        """
        ...

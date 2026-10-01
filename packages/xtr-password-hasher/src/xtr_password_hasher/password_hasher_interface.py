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

    A hash is opaque: it names its own algorithm, parameters and salt, so the
    same hasher — or one built from a later, stronger configuration — reads
    them back to verify and to decide whether the hash should be replaced. A
    hasher whose salt is stored beside the hash instead is a
    :class:`~xtr_password_hasher.LegacyPasswordHasherInterface`.
    """

    def hash(self, plain_password: str) -> str:
        """Hash ``plain_password`` and return the hash to store.

        Args:
            plain_password: The plaintext password.

        Raises:
            InvalidPasswordError: When ``plain_password`` is longer than
                :data:`MAX_PASSWORD_LENGTH`.
        """
        ...

    def verify(self, hashed_password: str, plain_password: str) -> bool:
        """Return whether ``plain_password`` is the password ``hashed_password`` was made from.

        Never raises for an over-long ``plain_password``: it cannot match a hash
        of a bounded input, so the answer is ``False``. The comparison is
        constant-time.
        """
        ...

    def needs_rehash(self, hashed_password: str) -> bool:
        """Return whether ``hashed_password`` should be replaced by a fresh hash.

        True when ``hashed_password`` was made by a weaker algorithm or with weaker
        parameters than this hasher now uses — the moment to rehash the
        plaintext, which is only in hand right after a successful verify.
        """
        ...

"""A hasher whose rehash answer and failures a test can choose.

The shipped plaintext hasher never asks to be rehashed, so it cannot exercise
the opportunistic upgrade the client repository does after a successful verify.
This one can: it hashes by prefixing, which makes a hash readable in an
assertion, and it counts its calls so a test can tell a rehash apart from the
verify that preceded it.
"""

from __future__ import annotations

import hmac
from typing import final

__all__ = ["RecordingPasswordHasher"]


@final
class RecordingPasswordHasher:
    """Hashes by prefixing, verifies in constant time, rehashes on demand."""

    __slots__ = ("_prefix", "_stale_prefix", "hash_calls", "verify_calls")

    def __init__(self, prefix: str = "v2", stale_prefix: str = "v1") -> None:
        """Hash under ``prefix``; call a hash made under ``stale_prefix`` stale."""
        self._prefix = prefix
        self._stale_prefix = stale_prefix
        self.hash_calls = 0
        self.verify_calls = 0

    def hash(self, plain_password: str) -> str:
        """Return ``plain_password`` under the current prefix."""
        self.hash_calls += 1
        return f"{self._prefix}${plain_password}"

    def verify(self, hashed_password: str, plain_password: str) -> bool:
        """Return whether ``hashed_password`` was made from ``plain_password``."""
        self.verify_calls += 1
        prefix, _, stored = hashed_password.partition("$")
        if prefix not in {self._prefix, self._stale_prefix}:
            return False

        return hmac.compare_digest(stored.encode(), plain_password.encode())

    def needs_rehash(self, hashed_password: str) -> bool:
        """Return whether ``hashed_password`` was made under the stale prefix."""
        return hashed_password.startswith(f"{self._stale_prefix}$")

"""PBKDF2 hashing with an external salt, for reading hashes of older schemes."""

from __future__ import annotations

import base64
import hashlib
import hmac
import math
from typing import final

from typing_extensions import override

from xtr_password_hasher.exception import InvalidArgumentError
from xtr_password_hasher.legacy_password_hasher_interface import LegacyPasswordHasherInterface

from ._password_length import ensure_within_length, is_within_length

__all__ = ["Pbkdf2PasswordHasher"]


@final
class Pbkdf2PasswordHasher(LegacyPasswordHasherInterface):
    """Derives a key with PBKDF2-HMAC and stores only the encoded key.

    The hash is the derived key alone — base64, or hex — so the salt lives
    beside it and the algorithm, the work factor and the key length live in
    this hasher's configuration. That is the shape of hashes many older
    applications stored; this hasher exists to verify them, and its defaults
    are the ones those hashes were typically made with. A ``None`` salt hashes
    with an empty one.

    Since the hash carries no parameters, :meth:`needs_rehash` cannot tell a
    weak hash from a strong one and always answers ``False``; put this hasher
    behind a self-salting one in a
    :class:`~xtr_password_hasher.MigratingPasswordHasher` to upgrade what it
    verifies.
    """

    __slots__ = (
        "_algorithm",
        "_encode_hash_as_base64",
        "_encoded_length",
        "_iterations",
        "_length",
    )

    def __init__(
        self,
        algorithm: str = "sha512",
        encode_hash_as_base64: bool = True,
        iterations: int = 1000,
        length: int = 40,
    ) -> None:
        """Configure the digest, the encoding, the work factor and the derived-key length.

        Args:
            algorithm: The digest PBKDF2 runs HMAC over.
            encode_hash_as_base64: Encode the derived key as base64; as hex
                when ``False``.
            iterations: How many times the digest is applied.
            length: The derived key's length, in bytes.

        Raises:
            InvalidArgumentError: When PBKDF2 cannot run ``algorithm`` on this
                platform, or the iteration count or key length is not positive.
        """
        if iterations < 1:
            raise InvalidArgumentError(f"PBKDF2 needs at least one iteration, not {iterations}.")
        if length < 1:
            raise InvalidArgumentError(f"The derived key length must be positive, not {length}.")
        try:
            _ = hashlib.pbkdf2_hmac(algorithm, b"", b"", 1, 1)
        except ValueError:
            raise InvalidArgumentError(
                f'The hash algorithm "{algorithm}" is not available on this platform.',
            ) from None
        self._algorithm = algorithm
        self._encode_hash_as_base64 = encode_hash_as_base64
        self._iterations = iterations
        self._length = length
        self._encoded_length = 4 * math.ceil(length / 3) if encode_hash_as_base64 else 2 * length

    @override
    def hash(self, plain_password: str, salt: str | None = None) -> str:
        """Derive a key from ``plain_password`` under ``salt`` and encode it.

        Raises:
            InvalidPasswordError: When ``plain_password`` is too long.
        """
        ensure_within_length(plain_password)
        derived = hashlib.pbkdf2_hmac(
            self._algorithm,
            plain_password.encode(),
            (salt or "").encode(),
            self._iterations,
            self._length,
        )
        if self._encode_hash_as_base64:
            return base64.b64encode(derived).decode("ascii")
        return derived.hex()

    @override
    def verify(
        self,
        hashed_password: str,
        plain_password: str,
        salt: str | None = None,
    ) -> bool:
        """Return whether ``plain_password`` under ``salt`` derives to ``hashed_password``.

        A hash of the wrong length, or one in a ``$``-delimited format, is
        rejected before any key is derived.
        """
        if len(hashed_password) != self._encoded_length or "$" in hashed_password:
            return False
        if not is_within_length(plain_password):
            return False
        return hmac.compare_digest(
            hashed_password.encode(),
            self.hash(plain_password, salt).encode(),
        )

    @override
    def needs_rehash(self, hashed_password: str) -> bool:
        """Return ``False``: the hash carries no parameters to compare."""
        del hashed_password
        return False

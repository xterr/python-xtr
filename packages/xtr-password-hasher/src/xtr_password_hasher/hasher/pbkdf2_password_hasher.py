"""PBKDF2 hashing on top of the standard library."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from typing import Final, final

from typing_extensions import override

from xtr_password_hasher.exception import InvalidArgumentError
from xtr_password_hasher.password_hasher_interface import PasswordHasherInterface

from ._password_length import ensure_within_length, is_within_length

__all__ = ["Pbkdf2PasswordHasher"]

_PREFIX: Final = "pbkdf2"
_SALT_BYTES: Final = 16
_MIN_ITERATIONS: Final = 1000
_ENCODED_PARTS: Final = 5


@final
class Pbkdf2PasswordHasher(PasswordHasherInterface):
    """Derives a key with PBKDF2-HMAC and stores it in a self-describing string.

    The hash reads ``$pbkdf2-<alg>$<iterations>$<salt>$<key>``, the salt and
    the derived key base64-encoded. Everything needed to verify — the digest,
    the work factor, the salt — travels in the string, so a hash made with one
    setting still verifies after the hasher is reconfigured, and
    :meth:`needs_rehash` sees the difference.

    PBKDF2 is offered for interoperability and for platforms without argon2 or
    bcrypt; argon2id (:class:`NativePasswordHasher`) is the stronger default.
    """

    __slots__ = ("_hash_algorithm", "_iterations", "_key_length")

    def __init__(
        self,
        hash_algorithm: str = "sha512",
        iterations: int = 210_000,
        key_length: int = 64,
    ) -> None:
        """Configure the digest, the work factor and the derived-key length.

        Raises:
            InvalidArgumentError: When the algorithm is not one the platform
                provides, the iteration count is below a safe floor, or the
                key length is not positive.
        """
        if hash_algorithm not in hashlib.algorithms_available:
            raise InvalidArgumentError(
                f'The hash algorithm "{hash_algorithm}" is not available on this platform.',
            )
        if iterations < _MIN_ITERATIONS:
            raise InvalidArgumentError(
                f"PBKDF2 needs at least {_MIN_ITERATIONS} iterations, not {iterations}.",
            )
        if key_length < 1:
            raise InvalidArgumentError(
                f"The derived key length must be positive, not {key_length}.",
            )
        self._hash_algorithm = hash_algorithm
        self._iterations = iterations
        self._key_length = key_length

    @override
    def hash(self, plain: str) -> str:
        """Derive a key from ``plain`` under a fresh salt and encode it.

        Raises:
            InvalidPasswordError: When ``plain`` is too long.
        """
        ensure_within_length(plain)
        salt = secrets.token_bytes(_SALT_BYTES)
        derived = self._derive(plain, salt)
        return self._encode(self._hash_algorithm, self._iterations, salt, derived)

    @override
    def verify(self, hashed: str, plain: str) -> bool:
        """Return whether ``plain`` derives to the key stored in ``hashed``."""
        if not is_within_length(plain):
            return False
        parsed = self._parse(hashed)
        if parsed is None:
            return False
        algorithm, iterations, salt, expected = parsed
        try:
            derived = hashlib.pbkdf2_hmac(
                algorithm, plain.encode(), salt, iterations, len(expected)
            )
        except (ValueError, TypeError):
            return False
        return hmac.compare_digest(derived, expected)

    @override
    def needs_rehash(self, hashed: str) -> bool:
        """Return whether ``hashed`` uses weaker parameters than configured."""
        parsed = self._parse(hashed)
        if parsed is None:
            return True
        algorithm, iterations, _salt, expected = parsed
        return (
            algorithm != self._hash_algorithm
            or iterations != self._iterations
            or len(expected) != self._key_length
        )

    def _derive(self, plain: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac(
            self._hash_algorithm,
            plain.encode(),
            salt,
            self._iterations,
            self._key_length,
        )

    @staticmethod
    def _encode(algorithm: str, iterations: int, salt: bytes, derived: bytes) -> str:
        salt_b64 = base64.b64encode(salt).decode("ascii")
        key_b64 = base64.b64encode(derived).decode("ascii")
        return f"${_PREFIX}-{algorithm}${iterations}${salt_b64}${key_b64}"

    @staticmethod
    def _parse(hashed: str) -> tuple[str, int, bytes, bytes] | None:
        parts = hashed.split("$")
        if len(parts) != _ENCODED_PARTS or parts[0] != "":
            return None
        scheme, iterations_text, salt_b64, key_b64 = parts[1], parts[2], parts[3], parts[4]
        if not scheme.startswith(f"{_PREFIX}-"):
            return None
        algorithm = scheme[len(_PREFIX) + 1 :]
        if not algorithm:
            return None
        try:
            iterations = int(iterations_text)
            salt = base64.b64decode(salt_b64, validate=True)
            expected = base64.b64decode(key_b64, validate=True)
        except (ValueError, TypeError):
            return None
        if iterations < 1 or not salt or not expected:
            return None
        return algorithm, iterations, salt, expected

"""Guard the one length every hasher shares.

An unbounded plaintext would let a caller spend a hasher's whole cost on a
single call; refusing it before any work is a denial-of-service guard, not a
policy on password length. The bound is on the UTF-8 byte length — the work a
hasher actually does is proportional to the bytes it reads, so a multi-byte
character costs its bytes, not one. Hashing raises; verifying an over-long
input simply cannot match a hash of a bounded one, so it returns ``False``.
"""

from __future__ import annotations

from xtr_password_hasher.exception import InvalidPasswordError
from xtr_password_hasher.password_hasher_interface import MAX_PASSWORD_LENGTH

__all__ = ["ensure_within_length", "is_within_length"]


def is_within_length(plain: str) -> bool:
    """Return whether ``plain`` is short enough, in UTF-8 bytes, to hash or verify."""
    return len(plain.encode("utf-8")) <= MAX_PASSWORD_LENGTH


def ensure_within_length(plain: str) -> None:
    """Refuse ``plain`` when its UTF-8 byte length crosses the shared limit.

    Raises:
        InvalidPasswordError: When ``plain`` encodes to more than
            :data:`~xtr_password_hasher.MAX_PASSWORD_LENGTH` UTF-8 bytes.
    """
    byte_length = len(plain.encode("utf-8"))
    if byte_length > MAX_PASSWORD_LENGTH:
        raise InvalidPasswordError(byte_length, MAX_PASSWORD_LENGTH)

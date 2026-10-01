"""The recommended hasher: argon2id by default, bcrypt on request."""

from __future__ import annotations

import base64
import hashlib
from typing import TYPE_CHECKING, Final, Literal, final

from typing_extensions import override

from xtr_password_hasher.exception import InvalidArgumentError
from xtr_password_hasher.password_hasher_interface import PasswordHasherInterface

from ._password_length import ensure_within_length, is_within_length

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["NativePasswordHasher"]

Algorithm = Literal["argon2id", "bcrypt"]

_BCRYPT_MAX_BYTES: Final = 72
_BCRYPT_MIN_COST: Final = 4
_BCRYPT_MAX_COST: Final = 31
_MIN_ARGON2_COST: Final = 1


@final
class _Backend:
    """One pwdlib hasher plus the three questions the native hasher asks it."""

    __slots__ = ("check_needs_rehash", "hash", "identify", "verify")

    def __init__(
        self,
        hash_one: Callable[[str], str],
        verify_one: Callable[[str, str], bool],
        identify: Callable[[str], bool],
        check_needs_rehash: Callable[[str], bool],
    ) -> None:
        self.hash = hash_one
        self.verify = verify_one
        self.identify = identify
        self.check_needs_rehash = check_needs_rehash


@final
class NativePasswordHasher(PasswordHasherInterface):
    """Hashes with argon2id or bcrypt, and verifies either when its backend is installed.

    Argon2id is the default: memory-hard, so a stolen hash is dear to attack on
    commodity hardware. bcrypt is available for interoperability — it needs the
    ``bcrypt`` extra — and, because bcrypt reads at most 72 bytes, a longer
    input is folded to a fixed length first (the base64 of its SHA-512 digest,
    truncated to what bcrypt reads) on both hashing and verifying, so a long
    password stays stable across the two.

    Whichever algorithm it hashes with, it verifies a hash of either as long as
    that algorithm's backend is present, so hashes minted by another stack —
    ``$argon2id$…`` or ``$2a$``/``$2b$``/``$2y$`` — migrate in place.
    :meth:`needs_rehash` asks for a fresh hash whenever a stored one is of the
    other algorithm, or of weaker parameters.
    """

    __slots__ = ("_algorithm", "_argon2", "_backend", "_bcrypt")

    def __init__(
        self,
        algorithm: Algorithm = "argon2id",
        *,
        time_cost: int = 3,
        memory_cost: int = 65536,
        parallelism: int = 4,
        cost: int = 12,
    ) -> None:
        """Configure the active algorithm and every backend that is installed.

        The active ``algorithm`` decides how :meth:`hash` writes; both backends
        are prepared for verifying when their libraries are present, so a
        migrating deployment reads legacy hashes of either.

        Raises:
            InvalidArgumentError: When ``algorithm`` is neither ``"argon2id"``
                nor ``"bcrypt"``, an argon2 cost is not positive, the bcrypt
                cost is outside 4 to 31, or ``algorithm="bcrypt"`` is asked for
                without the ``bcrypt`` extra installed.
        """
        if algorithm not in ("argon2id", "bcrypt"):
            raise InvalidArgumentError(  # pyright: ignore[reportUnreachable] -- guards an untyped caller
                f'The algorithm must be "argon2id" or "bcrypt", not "{algorithm}".',
            )
        _check_argon2_costs(time_cost, memory_cost, parallelism)
        _check_bcrypt_cost(cost)

        self._algorithm: Algorithm = algorithm
        self._argon2 = _make_argon2_backend(time_cost, memory_cost, parallelism)
        self._bcrypt = _make_bcrypt_backend(cost)

        if algorithm == "argon2id":
            self._backend = self._argon2
        elif self._bcrypt is not None:
            self._backend = self._bcrypt
        else:
            raise InvalidArgumentError(
                'The "bcrypt" algorithm needs the bcrypt extra: install '
                '"xtr-password-hasher[bcrypt]".',
            )

    @override
    def hash(self, plain: str) -> str:
        """Hash ``plain`` with the active algorithm.

        Raises:
            InvalidPasswordError: When ``plain`` is too long.
        """
        ensure_within_length(plain)
        return self._backend.hash(plain)

    @override
    def verify(self, hashed: str, plain: str) -> bool:
        """Return whether ``plain`` made ``hashed``, using whichever backend owns it."""
        if not is_within_length(plain):
            return False
        backend = self._backend_for(hashed)
        if backend is None:
            return False
        return backend.verify(hashed, plain)

    @override
    def needs_rehash(self, hashed: str) -> bool:
        """Return whether ``hashed`` should be replaced by a fresh hash.

        True when ``hashed`` belongs to the other algorithm, is unrecognised,
        or was made with weaker parameters than the active backend now uses.
        """
        if not self._backend.identify(hashed):
            return True
        return self._backend.check_needs_rehash(hashed)

    def _backend_for(self, hashed: str) -> _Backend | None:
        if self._argon2.identify(hashed):
            return self._argon2
        if self._bcrypt is not None and self._bcrypt.identify(hashed):
            return self._bcrypt
        return None


def _check_argon2_costs(time_cost: int, memory_cost: int, parallelism: int) -> None:
    for name, value in (
        ("time_cost", time_cost),
        ("memory_cost", memory_cost),
        ("parallelism", parallelism),
    ):
        if value < _MIN_ARGON2_COST:
            raise InvalidArgumentError(f"The argon2 {name} must be positive, not {value}.")


def _check_bcrypt_cost(cost: int) -> None:
    if not _BCRYPT_MIN_COST <= cost <= _BCRYPT_MAX_COST:
        raise InvalidArgumentError(
            f"The bcrypt cost must be between {_BCRYPT_MIN_COST} and {_BCRYPT_MAX_COST}, "
            f"not {cost}.",
        )


def _make_argon2_backend(time_cost: int, memory_cost: int, parallelism: int) -> _Backend:
    from pwdlib.hashers.argon2 import Argon2Hasher  # noqa: PLC0415 — argon2 is a core dependency

    hasher = Argon2Hasher(
        time_cost=time_cost,
        memory_cost=memory_cost,
        parallelism=parallelism,
    )
    return _Backend(
        hash_one=hasher.hash,
        verify_one=lambda hashed, plain: hasher.verify(plain, hashed),
        identify=Argon2Hasher.identify,
        check_needs_rehash=hasher.check_needs_rehash,
    )


def _make_bcrypt_backend(cost: int) -> _Backend | None:
    from pwdlib.exceptions import HasherNotAvailable  # noqa: PLC0415 — optional extra

    try:
        # pwdlib raises HasherNotAvailable (not ImportError) at import when bcrypt is absent.
        from pwdlib.hashers.bcrypt import BcryptHasher  # noqa: PLC0415 — optional extra
    except (ImportError, HasherNotAvailable):
        return None

    hasher = BcryptHasher(rounds=cost)

    def hash_one(plain: str) -> str:
        return hasher.hash(_fold_for_bcrypt(plain))

    def verify_one(hashed: str, plain: str) -> bool:
        return hasher.verify(_fold_for_bcrypt(plain), hashed)

    return _Backend(
        hash_one=hash_one,
        verify_one=verify_one,
        identify=BcryptHasher.identify,
        check_needs_rehash=hasher.check_needs_rehash,
    )


def _fold_for_bcrypt(plain: str) -> str:
    """Fold an over-72-byte password to what bcrypt reads, stably.

    bcrypt reads at most 72 bytes and pwdlib refuses a longer input outright.
    A longer password is replaced by the base64 of its SHA-512 digest, cut to
    the 72 bytes bcrypt would itself have kept — so hashing and verifying agree,
    and a hash another stack made the same way still verifies.
    """
    encoded = plain.encode("utf-8")
    if len(encoded) <= _BCRYPT_MAX_BYTES:
        return plain
    digest = base64.b64encode(hashlib.sha512(encoded).digest()).decode("ascii")
    return digest[:_BCRYPT_MAX_BYTES]

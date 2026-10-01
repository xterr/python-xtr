"""Password hashers described as inert data, told apart by their ``type``.

Each config is a frozen dataclass carrying the settings one hasher needs, tagged
by a ``type`` discriminator — ``type="native"``. Every value is checked as the
config is made, so a bad bcrypt cost or an unknown digest fails where it is
written, not on the first hash. The bundle turns a config into a live hasher and
a :class:`ServiceHasherConfig` into the service it names; the hasher package
itself carries no configuration vocabulary and takes ready hashers.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from xtr_password_hasher.exception import InvalidArgumentError

if TYPE_CHECKING:
    import builtins

__all__ = [
    "AutoHasherConfig",
    "HasherConfig",
    "NativeHasherConfig",
    "Pbkdf2HasherConfig",
    "PlaintextHasherConfig",
    "ServiceHasherConfig",
]

_BCRYPT_MIN_COST = 4
_BCRYPT_MAX_COST = 31


@dataclass(frozen=True, slots=True, kw_only=True)
class AutoHasherConfig:
    """The secure default: argon2id, verifying bcrypt and PBKDF2 behind it.

    Built into a migrating hasher whose best is argon2id, whose extras are
    bcrypt (only when that backend is installed) and PBKDF2 — so a fresh
    password is argon2id and a legacy one still verifies and is upgraded.
    """

    type: Literal["auto"] = "auto"


@dataclass(frozen=True, slots=True, kw_only=True)
class NativeHasherConfig:
    """An argon2id or bcrypt hasher, optionally migrating older hashes.

    ``migrate_from`` names hashers whose hashes this one should still verify
    and upgrade: the config is built into a migrating hasher, best first.

    Raises:
        InvalidArgumentError: On an unknown algorithm, a non-positive argon2
            cost, or a bcrypt cost outside 4 to 31.
    """

    type: Literal["native"] = "native"
    algorithm: Literal["argon2id", "bcrypt"] = "argon2id"
    time_cost: int = 3
    memory_cost: int = 65536
    parallelism: int = 4
    cost: int = 12
    migrate_from: tuple[HasherConfig, ...] = ()

    def __post_init__(self) -> None:
        """Check the algorithm and its costs as the config is written."""
        if self.algorithm not in ("argon2id", "bcrypt"):
            raise InvalidArgumentError(
                f'The algorithm must be "argon2id" or "bcrypt", not "{self.algorithm}".',
            )
        for name, value in (
            ("time_cost", self.time_cost),
            ("memory_cost", self.memory_cost),
            ("parallelism", self.parallelism),
        ):
            if value < 1:
                raise InvalidArgumentError(f"The argon2 {name} must be positive, not {value}.")
        if not _BCRYPT_MIN_COST <= self.cost <= _BCRYPT_MAX_COST:
            raise InvalidArgumentError(
                f"The bcrypt cost must be between {_BCRYPT_MIN_COST} and {_BCRYPT_MAX_COST}, "
                f"not {self.cost}.",
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class Pbkdf2HasherConfig:
    """A PBKDF2 hasher, for verifying hashes stored with a salt of their own.

    The defaults match the hashes such schemes typically stored. The hash
    carries no parameters, so this hasher never asks for a rehash; reach it
    through another config's ``migrate_from`` to upgrade what it verifies.

    Raises:
        InvalidArgumentError: On a digest the platform does not provide, or a
            non-positive iteration count or key length.
    """

    type: Literal["pbkdf2"] = "pbkdf2"
    hash_algorithm: str = "sha512"
    encode_as_base64: bool = True
    iterations: int = 1000
    key_length: int = 40
    migrate_from: tuple[HasherConfig, ...] = ()

    def __post_init__(self) -> None:
        """Check the digest, the work factor and the key length as the config is written."""
        try:
            _ = hashlib.pbkdf2_hmac(self.hash_algorithm, b"", b"", 1, 1)
        except ValueError:
            raise InvalidArgumentError(
                f'The hash algorithm "{self.hash_algorithm}" is not available on this platform.',
            ) from None
        if self.iterations < 1:
            raise InvalidArgumentError(
                f"PBKDF2 needs at least one iteration, not {self.iterations}.",
            )
        if self.key_length < 1:
            raise InvalidArgumentError(
                f"The derived key length must be positive, not {self.key_length}.",
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class PlaintextHasherConfig:
    """A hasher that stores the password in the clear — for tests only.

    ``ignore_case`` compares passwords case-insensitively.
    """

    type: Literal["plaintext"] = "plaintext"
    ignore_case: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class ServiceHasherConfig:
    """A hasher the container provides, named by its type and an optional qualifier.

    The bundle resolves it from the container; built outside a container it has
    no service to fetch, so the plain builder refuses it.

    Raises:
        InvalidArgumentError: When ``service`` is not a class.
    """

    service: builtins.type
    type: Literal["service"] = "service"
    qualifier: str | None = None

    def __post_init__(self) -> None:
        """Check ``service`` is a class as the config is written."""
        if not isinstance(self.service, type):  # pyright: ignore[reportUnnecessaryIsInstance] -- configs are written by hand; the annotation is not enforced
            raise InvalidArgumentError(
                f"A service hasher config needs a class, not {self.service!r}.",
            )


HasherConfig = (
    AutoHasherConfig
    | NativeHasherConfig
    | Pbkdf2HasherConfig
    | PlaintextHasherConfig
    | ServiceHasherConfig
)
"""Every kind of hasher config, told apart by its ``type`` field."""

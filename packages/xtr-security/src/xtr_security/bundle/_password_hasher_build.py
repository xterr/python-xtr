"""Turn a hasher config into a live hasher, for the security bundle to register.

Every config but :class:`ServiceHasherConfig` builds without a container — the
bundle resolves that one from the service it names. This is where a config's
``migrate_from`` becomes a migrating hasher, and where the ``auto`` config
expands into argon2id with bcrypt and PBKDF2 behind it, through the hasher
package's own :func:`create_auto_password_hasher` so the two never drift.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, assert_never

from xtr_password_hasher import (
    MigratingPasswordHasher,
    NativePasswordHasher,
    Pbkdf2PasswordHasher,
    PlaintextPasswordHasher,
    create_auto_password_hasher,
)
from xtr_password_hasher.exception import InvalidArgumentError

from .password_hasher_configs import (
    AutoHasherConfig,
    NativeHasherConfig,
    Pbkdf2HasherConfig,
    PlaintextHasherConfig,
    ServiceHasherConfig,
)

if TYPE_CHECKING:
    from xtr_password_hasher import PasswordHasherInterface

    from .password_hasher_configs import HasherConfig

__all__ = ["build_hasher"]


def build_hasher(config: HasherConfig) -> PasswordHasherInterface:
    """Build the hasher ``config`` describes.

    Raises:
        InvalidArgumentError: For a :class:`ServiceHasherConfig`, which only a
            container can resolve; use the bundle instead.
    """
    match config:
        case AutoHasherConfig():
            return create_auto_password_hasher()
        case NativeHasherConfig():
            base = NativePasswordHasher(
                config.algorithm,
                time_cost=config.time_cost,
                memory_cost=config.memory_cost,
                parallelism=config.parallelism,
                cost=config.cost,
            )
            return _migrating(base, config.migrate_from)
        case Pbkdf2HasherConfig():
            base = Pbkdf2PasswordHasher(
                hash_algorithm=config.hash_algorithm,
                iterations=config.iterations,
                key_length=config.key_length,
            )
            return _migrating(base, config.migrate_from)
        case PlaintextHasherConfig():
            return PlaintextPasswordHasher()
        case ServiceHasherConfig():
            raise InvalidArgumentError(
                "A service hasher config is resolved from the container by the bundle, "
                "not built directly.",
            )
        case _:
            assert_never(config)


def _migrating(
    base: PasswordHasherInterface,
    migrate_from: tuple[HasherConfig, ...],
) -> PasswordHasherInterface:
    if not migrate_from:
        return base
    return MigratingPasswordHasher(base, *(build_hasher(config) for config in migrate_from))

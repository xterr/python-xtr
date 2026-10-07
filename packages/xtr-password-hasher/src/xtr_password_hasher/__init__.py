"""Password hashing behind one interface.

argon2id by default, legacy hashes verified and upgraded.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .exception import (
    InvalidArgumentError,
    InvalidPasswordError,
    PasswordHasherError,
    UnknownPasswordHasherError,
)
from .hasher.create_auto_password_hasher import bcrypt_available, create_auto_password_hasher
from .hasher.migrating_password_hasher import MigratingPasswordHasher
from .hasher.native_password_hasher import NativePasswordHasher
from .hasher.password_hasher_aware_interface import PasswordHasherAwareInterface
from .hasher.password_hasher_factory import PasswordHasherFactory
from .hasher.password_hasher_factory_interface import PasswordHasherFactoryInterface
from .hasher.pbkdf2_password_hasher import Pbkdf2PasswordHasher
from .hasher.plaintext_password_hasher import PlaintextPasswordHasher
from .hasher.user_password_hasher import UserPasswordHasher
from .hasher.user_password_hasher_interface import UserPasswordHasherInterface
from .legacy_password_authenticated_user_interface import LegacyPasswordAuthenticatedUserInterface
from .legacy_password_hasher_interface import (
    LegacyPasswordHasherInterface,
    is_legacy_password_hasher,
)
from .password_authenticated_user_interface import PasswordAuthenticatedUserInterface
from .password_hasher_interface import MAX_PASSWORD_LENGTH, PasswordHasherInterface

__all__ = [
    "MAX_PASSWORD_LENGTH",
    "InvalidArgumentError",
    "InvalidPasswordError",
    "LegacyPasswordAuthenticatedUserInterface",
    "LegacyPasswordHasherInterface",
    "MigratingPasswordHasher",
    "NativePasswordHasher",
    "PasswordAuthenticatedUserInterface",
    "PasswordHasherAwareInterface",
    "PasswordHasherError",
    "PasswordHasherFactory",
    "PasswordHasherFactoryInterface",
    "PasswordHasherInterface",
    "Pbkdf2PasswordHasher",
    "PlaintextPasswordHasher",
    "UnknownPasswordHasherError",
    "UserPasswordHasher",
    "UserPasswordHasherInterface",
    "__version__",
    "bcrypt_available",
    "create_auto_password_hasher",
    "is_legacy_password_hasher",
]

try:
    __version__ = version("xtr-password-hasher")
except PackageNotFoundError:  # pragma: no cover
    # Running from a source tree with no installed metadata to read; having no
    # version is better than refusing to import.
    __version__ = "0+unknown"

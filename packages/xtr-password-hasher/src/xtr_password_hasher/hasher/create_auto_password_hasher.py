"""Build the secure default hasher: argon2id, verifying bcrypt and PBKDF2 behind it.

The one composition an application gets when it asks for no particular hasher —
a migrating hasher whose best is argon2id, whose extras are bcrypt (only when
that backend is installed) and PBKDF2. The console command uses it with no
container, and the security bundle builds its ``auto`` hasher configuration from
it, so the two never drift.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from .migrating_password_hasher import MigratingPasswordHasher
from .native_password_hasher import NativePasswordHasher
from .pbkdf2_password_hasher import Pbkdf2PasswordHasher

if TYPE_CHECKING:
    from xtr_password_hasher.password_hasher_interface import PasswordHasherInterface

__all__ = ["bcrypt_available", "create_auto_password_hasher"]


def bcrypt_available() -> bool:
    """Return whether the bcrypt backend can actually be loaded.

    pwdlib ships the ``pwdlib.hashers.bcrypt`` module whether or not the
    ``bcrypt`` library behind it is installed, so merely finding the module
    answers ``True`` for a missing backend. An import probe — importing it, the
    way the native hasher builds its backend — is the reliable check: it raises
    when ``bcrypt`` is absent.
    """
    from pwdlib.exceptions import HasherNotAvailable  # noqa: PLC0415 — optional extra

    try:
        _ = importlib.import_module("pwdlib.hashers.bcrypt")
    except (ImportError, HasherNotAvailable):
        return False
    return True


def create_auto_password_hasher() -> PasswordHasherInterface:
    """Build argon2id with bcrypt (when installed) and PBKDF2 verifying behind it."""
    extras: list[PasswordHasherInterface] = []
    if bcrypt_available():
        extras.append(NativePasswordHasher("bcrypt"))
    extras.append(Pbkdf2PasswordHasher())
    return MigratingPasswordHasher(NativePasswordHasher("argon2id"), *extras)

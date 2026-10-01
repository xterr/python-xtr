"""Every error this library raises, all deriving from :class:`PasswordHasherError`."""

from __future__ import annotations

from .invalid_argument_error import InvalidArgumentError
from .invalid_password_error import InvalidPasswordError
from .password_hasher_error import PasswordHasherError
from .unknown_password_hasher_error import UnknownPasswordHasherError

__all__ = [
    "InvalidArgumentError",
    "InvalidPasswordError",
    "PasswordHasherError",
    "UnknownPasswordHasherError",
]

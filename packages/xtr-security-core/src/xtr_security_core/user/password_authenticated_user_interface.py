"""The user that carries a hashed password.

The contract is owned by :mod:`xtr_password_hasher`, which this package builds
on and which hashes and verifies against it; it is re-exported here so a user
contract is imported from where the other user contracts live.
"""

from __future__ import annotations

from xtr_password_hasher import PasswordAuthenticatedUserInterface

__all__ = ["PasswordAuthenticatedUserInterface"]

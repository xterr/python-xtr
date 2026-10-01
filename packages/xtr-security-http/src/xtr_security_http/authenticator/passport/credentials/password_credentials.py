"""A plaintext password to verify, consumed once."""

from __future__ import annotations

from typing import final

from typing_extensions import override
from xtr_security_core.exception import InvalidArgumentError

from .credentials_interface import CredentialsInterface

__all__ = ["PasswordCredentials"]


@final
class PasswordCredentials(CredentialsInterface):
    """A plaintext password waiting to be verified.

    Carried on a passport for the credentials listener to check against the
    user's stored hash. Verifying it calls :meth:`mark_resolved`, which drops
    the plaintext: it is held only until the one check that reads it, never
    longer. Reading the plaintext after it is resolved is refused.
    """

    __slots__ = ("_password", "_resolved")

    def __init__(self, password: str) -> None:
        """Record the plaintext password to verify."""
        self._password = password
        self._resolved = False

    def get_password(self) -> str:
        """Return the plaintext to verify, before it is consumed.

        Raises:
            InvalidArgumentError: When the credentials are already resolved and
                the plaintext has been dropped.
        """
        if self._resolved:
            raise InvalidArgumentError("The password credentials have already been resolved.")
        return self._password

    def mark_resolved(self) -> None:
        """Mark the credentials verified and drop the plaintext."""
        self._resolved = True
        self._password = ""

    @override
    def is_resolved(self) -> bool:
        """Tell whether the credentials have been verified."""
        return self._resolved

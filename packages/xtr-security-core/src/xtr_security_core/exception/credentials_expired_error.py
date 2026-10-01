"""The account's credentials have expired."""

from __future__ import annotations

from typing import ClassVar

from .account_status_error import AccountStatusError

__all__ = ["CredentialsExpiredError"]


class CredentialsExpiredError(AccountStatusError):
    """The account's credentials have expired and must be renewed."""

    MESSAGE_KEY: ClassVar[str] = "Credentials have expired."

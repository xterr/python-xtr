"""The account is locked."""

from __future__ import annotations

from typing import ClassVar

from .account_status_error import AccountStatusError

__all__ = ["LockedError"]


class LockedError(AccountStatusError):
    """The account is locked and may not authenticate."""

    MESSAGE_KEY: ClassVar[str] = "Account is locked."

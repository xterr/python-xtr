"""The account has expired."""

from __future__ import annotations

from typing import ClassVar

from .account_status_error import AccountStatusError

__all__ = ["AccountExpiredError"]


class AccountExpiredError(AccountStatusError):
    """The account has expired and may no longer authenticate."""

    MESSAGE_KEY: ClassVar[str] = "Account has expired."

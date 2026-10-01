"""The account is disabled."""

from __future__ import annotations

from typing import ClassVar

from .account_status_error import AccountStatusError

__all__ = ["DisabledError"]


class DisabledError(AccountStatusError):
    """The account has been disabled and may not authenticate."""

    MESSAGE_KEY: ClassVar[str] = "Account is disabled."

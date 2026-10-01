"""An account-status failure carrying a message meant for the client."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .account_status_error import AccountStatusError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["CustomUserMessageAccountStatusError"]


class CustomUserMessageAccountStatusError(AccountStatusError):
    """An account-status failure whose public text is chosen at the raise site.

    Deliberately shown to the client rather than masked: a checker with a safe,
    specific reason ("your subscription has lapsed") raises this with that
    reason as the message key.
    """

    def __init__(
        self,
        message_key: str,
        *,
        user: UserInterface | None = None,
        message_data: Mapping[str, object] | None = None,
        message: str | None = None,
    ) -> None:
        """Record the public message key and the values it substitutes."""
        super().__init__(
            user,
            message if message is not None else message_key,
            message_key=message_key,
            message_data=message_data,
        )

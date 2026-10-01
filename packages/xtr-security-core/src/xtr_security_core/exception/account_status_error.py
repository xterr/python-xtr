"""The account exists and the credentials are right, but the account cannot be used."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .authentication_error import AuthenticationError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["AccountStatusError"]


class AccountStatusError(AuthenticationError):
    """Authentication is refused because of the account's own state.

    The credentials were correct: the account is disabled, locked, or expired.
    A user checker raises one of the subclasses; whether the client is told the
    real reason or only that its credentials failed is decided by the exposure
    level (see :func:`~xtr_security_core.authentication.is_sensitive`).

    Attributes:
        user: The user whose account state refused authentication.
    """

    user: UserInterface | None

    def __init__(
        self,
        user: UserInterface | None = None,
        message: str | None = None,
        *,
        message_key: str | None = None,
        message_data: Mapping[str, object] | None = None,
    ) -> None:
        """Record the user whose account state refused authentication."""
        self.user = user
        super().__init__(message, message_key=message_key, message_data=message_data)

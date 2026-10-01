"""An authentication failure carrying a message meant for the client."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .authentication_error import AuthenticationError

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["CustomUserMessageAuthenticationError"]


class CustomUserMessageAuthenticationError(AuthenticationError):
    """An authentication failure whose public text is chosen at the raise site.

    Where the ordinary errors mask their cause, this one is deliberately shown
    to the client: an authenticator that has a safe, specific reason to give
    ("your account is not yet activated") raises this with that reason as the
    message key.
    """

    def __init__(
        self,
        message_key: str,
        *,
        message_data: Mapping[str, object] | None = None,
        message: str | None = None,
    ) -> None:
        """Record the public message key and the values it substitutes."""
        super().__init__(
            message if message is not None else message_key,
            message_key=message_key,
            message_data=message_data,
        )

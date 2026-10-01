"""No user matched the identifier presented."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from .authentication_error import AuthenticationError

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["UserNotFoundError"]


class UserNotFoundError(AuthenticationError, LookupError):  # pyright: ignore[reportUnsafeMultipleInheritance] — LookupError adds no state; AuthenticationError.__init__ drives construction
    """No user matched the identifier presented.

    Also a :class:`LookupError`, so a provider's caller may treat a missing
    user like any other failed lookup. Its public key is
    ``"Bad credentials."`` rather than anything naming the identifier: telling
    a client that a user does not exist is a way to enumerate accounts, so the
    identifier stays on :attr:`user_identifier` for logs alone.

    Attributes:
        user_identifier: The identifier that matched no user.
    """

    MESSAGE_KEY: ClassVar[str] = "Bad credentials."

    user_identifier: str | None

    def __init__(
        self,
        user_identifier: str | None = None,
        message: str | None = None,
        *,
        message_data: Mapping[str, object] | None = None,
    ) -> None:
        """Record the identifier that matched no user."""
        self.user_identifier = user_identifier
        super().__init__(
            message if message is not None else f'User "{user_identifier}" not found.',
            message_data=message_data,
        )

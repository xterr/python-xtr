"""What decides whether an authenticated user may proceed."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["UserCheckerInterface"]


@runtime_checkable
class UserCheckerInterface(Protocol):
    """Gates a user's own state around authentication.

    Credentials being right is not the whole of authentication: the account may
    be disabled, locked or expired. A checker runs before credentials are
    checked and again after, raising an
    :class:`~xtr_security_core.exception.AccountStatusError` when the account itself
    forbids proceeding.
    """

    async def check_pre_auth(self, user: UserInterface) -> None:
        """Check ``user``'s state before its credentials are verified.

        Raises:
            AccountStatusError: When the account may not authenticate.
        """
        ...

    async def check_post_auth(
        self,
        user: UserInterface,
        token: TokenInterface | None = None,
    ) -> None:
        """Check ``user``'s state after authentication settled on ``token``.

        Raises:
            AccountStatusError: When the account may not proceed.
        """
        ...

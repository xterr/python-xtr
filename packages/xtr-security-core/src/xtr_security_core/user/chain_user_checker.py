"""A checker that runs several checkers in turn."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .user_checker_interface import UserCheckerInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["ChainUserChecker"]


@final
class ChainUserChecker(UserCheckerInterface):
    """Runs each checker in order, so the first refusal stops the rest.

    An application may gate a user on more than one condition — disabled, then
    locked out, then expired. Each checker runs in turn; the account-status
    error one raises propagates, and the checkers after it do not run.
    """

    __slots__ = ("_checkers",)

    def __init__(self, checkers: Sequence[UserCheckerInterface]) -> None:
        """Record the checkers to run, in order."""
        self._checkers: tuple[UserCheckerInterface, ...] = tuple(checkers)

    @override
    async def check_pre_auth(self, user: UserInterface) -> None:
        """Run every checker's pre-authentication check, in order.

        Raises:
            AccountStatusError: As soon as a checker refuses.
        """
        for checker in self._checkers:
            await checker.check_pre_auth(user)

    @override
    async def check_post_auth(
        self,
        user: UserInterface,
        token: TokenInterface | None = None,
    ) -> None:
        """Run every checker's post-authentication check, in order.

        Raises:
            AccountStatusError: As soon as a checker refuses.
        """
        for checker in self._checkers:
            await checker.check_post_auth(user, token)

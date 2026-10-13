"""What a closure attribute is handed to decide access with."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from .authorization_checker_interface import AuthorizationCheckerInterface
from .voter.authenticated_voter import AuthenticatedVoter

if TYPE_CHECKING:
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.user.user_interface import UserInterface

    from .access_decision import AccessDecision

__all__ = ["IsGrantedContext"]


class IsGrantedContext(AuthorizationCheckerInterface):
    """The token, its user, and an authorization checker to ask further questions.

    A closure attribute (see
    :class:`~xtr_security_core.authorization.voter.closure_voter.ClosureVoter`)
    receives one of these and the subject. It has the token and its user to
    reason about directly, :meth:`is_granted` to ask a nested question for the
    same token — "may this token edit *this* book?" — and shortcuts for the
    authentication-strength questions.

    Attributes:
        token: The token the decision is being made for.
        user: The token's user, or ``None`` when nobody is authenticated.
    """

    __slots__: tuple[str, ...] = ("_authorization_checker", "_token", "_user")

    _token: TokenInterface
    _user: UserInterface | None
    _authorization_checker: AuthorizationCheckerInterface

    def __init__(
        self,
        token: TokenInterface,
        user: UserInterface | None,
        authorization_checker: AuthorizationCheckerInterface,
    ) -> None:
        """Record the token, its user, and the checker nested questions go to."""
        self._token = token
        self._user = user
        self._authorization_checker = authorization_checker

    @property
    def token(self) -> TokenInterface:
        """The token the decision is being made for."""
        return self._token

    @property
    def user(self) -> UserInterface | None:
        """The token's user, or ``None`` when nobody is authenticated."""
        return self._user

    @override
    async def is_granted(
        self,
        attribute: object,
        subject: object = None,
        access_decision: AccessDecision | None = None,
    ) -> bool:
        """Answer a nested access question for the same token."""
        return await self._authorization_checker.is_granted(attribute, subject, access_decision)

    async def is_authenticated(self) -> bool:
        """Tell whether the token is authenticated."""
        return await self._authorization_checker.is_granted(AuthenticatedVoter.IS_AUTHENTICATED)

    async def is_authenticated_fully(self) -> bool:
        """Tell whether the token is fully authenticated."""
        return await self._authorization_checker.is_granted(
            AuthenticatedVoter.IS_AUTHENTICATED_FULLY
        )

    async def is_authenticated_recently(self) -> bool:
        """Tell whether the user authenticated recently."""
        return await self._authorization_checker.is_granted(
            AuthenticatedVoter.IS_AUTHENTICATED_RECENTLY
        )

    async def is_authenticated_very_recently(self) -> bool:
        """Tell whether the user authenticated very recently."""
        return await self._authorization_checker.is_granted(
            AuthenticatedVoter.IS_AUTHENTICATED_VERY_RECENTLY
        )

    async def is_impersonator(self) -> bool:
        """Tell whether the user is impersonating another user."""
        return await self._authorization_checker.is_granted(AuthenticatedVoter.IS_IMPERSONATOR)

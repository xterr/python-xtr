"""The security facade: the current caller, and what they may do."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_security_core.authorization.access_decision import AccessDecision
from xtr_security_core.authorization.authorization_checker_interface import (
    AuthorizationCheckerInterface,
)
from xtr_security_core.authorization.guest_authorization_checker_interface import (
    GuestAuthorizationCheckerInterface,
)
from xtr_security_core.exception import AccessDeniedError, UnsupportedUserError

if TYPE_CHECKING:
    from xtr_security_core.authentication.token.storage.token_storage_interface import (
        TokenStorageInterface,
    )
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["Security"]


@final
class Security(AuthorizationCheckerInterface, GuestAuthorizationCheckerInterface):
    """One object for the two everyday questions: who is calling, and may they.

    A thin front over the token storage and the authorization checker, so a
    controller or a service asks ``security.get_user()`` and
    ``await security.is_granted(...)`` without wiring both. It is itself an
    authorization checker — for the current caller and for a given user alike —
    so it stands in wherever one is wanted.
    """

    __slots__ = ("_authorization_checker", "_token_storage")

    def __init__(
        self,
        token_storage: TokenStorageInterface,
        authorization_checker: AuthorizationCheckerInterface,
    ) -> None:
        """Record where the current token lives and who answers authorization."""
        self._token_storage = token_storage
        self._authorization_checker = authorization_checker

    def get_token(self) -> TokenInterface | None:
        """Return the current token, or ``None`` when nobody is authenticated."""
        return self._token_storage.get_token()

    def get_user(self) -> UserInterface | None:
        """Return the current user, or ``None`` when nobody is authenticated."""
        token = self.get_token()
        return token.get_user() if token is not None else None

    @override
    async def is_granted(
        self,
        attribute: object,
        subject: object = None,
        access_decision: AccessDecision | None = None,
    ) -> bool:
        """Tell whether the current caller may have ``attribute`` over ``subject``."""
        return await self._authorization_checker.is_granted(attribute, subject, access_decision)

    @override
    async def is_granted_for_user(
        self,
        user: UserInterface,
        attribute: object,
        subject: object = None,
        access_decision: AccessDecision | None = None,
    ) -> bool:
        """Tell whether ``user`` may have ``attribute`` over ``subject``.

        Raises:
            UnsupportedUserError: When the checker cannot decide for a given
                user rather than only the current caller.
        """
        checker = self._authorization_checker
        if not isinstance(checker, GuestAuthorizationCheckerInterface):
            raise UnsupportedUserError(
                "The authorization checker cannot decide for a given user.",
            )
        return await checker.is_granted_for_user(user, attribute, subject, access_decision)

    async def deny_access_unless_granted(
        self,
        attribute: object,
        subject: object = None,
        message: str = "Access Denied.",
    ) -> None:
        """Raise unless the current caller may have ``attribute`` over ``subject``.

        Raises:
            AccessDeniedError: When access is not granted, carrying the decision
                that refused so a handler can explain it.
        """
        decision = AccessDecision()
        if not await self._authorization_checker.is_granted(attribute, subject, decision):
            raise AccessDeniedError(
                message,
                attributes=(attribute,),
                subject=subject,
                access_decision=decision,
            )

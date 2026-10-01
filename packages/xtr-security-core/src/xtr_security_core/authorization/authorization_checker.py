"""The authorization checker: decides against the current token, or a given user."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_core.authentication.token.null_token import NullToken
from xtr_security_core.authentication.token.username_password_token import UsernamePasswordToken

from .authorization_checker_interface import AuthorizationCheckerInterface
from .guest_authorization_checker_interface import GuestAuthorizationCheckerInterface

if TYPE_CHECKING:
    from xtr_security_core.authentication.token.storage.token_storage_interface import (
        TokenStorageInterface,
    )
    from xtr_security_core.user.user_interface import UserInterface

    from .access_decision import AccessDecision
    from .access_decision_manager_interface import AccessDecisionManagerInterface

__all__ = ["AuthorizationChecker"]

#: The firewall name on a token built for a user who is not the current caller.
_GUEST_FIREWALL: str = "__guest__"


@final
class AuthorizationChecker(AuthorizationCheckerInterface, GuestAuthorizationCheckerInterface):
    """Answers authorization questions for the current token, or for a given user.

    :meth:`is_granted` reads the token from the storage — the anonymous
    :class:`~xtr_security_core.authentication.token.null_token.NullToken` when none is
    set — so the everyday question needs no token in hand.
    :meth:`is_granted_for_user` steps outside the current caller: it builds a
    throwaway token from the user's own roles and decides against that, which is
    what a consent screen or a worker needs.
    """

    __slots__ = ("_access_decision_manager", "_token_storage")

    def __init__(
        self,
        token_storage: TokenStorageInterface,
        access_decision_manager: AccessDecisionManagerInterface,
    ) -> None:
        """Record where the current token lives and who decides."""
        self._token_storage = token_storage
        self._access_decision_manager = access_decision_manager

    @override
    async def is_granted(
        self,
        attribute: object,
        subject: object = None,
        access_decision: AccessDecision | None = None,
    ) -> bool:
        """Tell whether the current token may have ``attribute`` over ``subject``."""
        token = self._token_storage.get_token()
        if token is None:
            token = NullToken()
        return await self._access_decision_manager.decide(
            token,
            [attribute],
            subject,
            access_decision,
        )

    @override
    async def is_granted_for_user(
        self,
        user: UserInterface,
        attribute: object,
        subject: object = None,
        access_decision: AccessDecision | None = None,
    ) -> bool:
        """Tell whether ``user`` may have ``attribute`` over ``subject``."""
        token = UsernamePasswordToken(user, _GUEST_FIREWALL, list(user.get_roles()))
        return await self._access_decision_manager.decide(
            token,
            [attribute],
            subject,
            access_decision,
        )

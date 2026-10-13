"""The authorization checker: decides against the current token, or a given user."""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_core.authentication.token.abstract_token import AbstractToken
from xtr_security_core.authentication.token.null_token import NullToken
from xtr_security_core.authentication.token.offline_token_interface import OfflineTokenInterface

from .authorization_checker_interface import AuthorizationCheckerInterface
from .guest_authorization_checker_interface import GuestAuthorizationCheckerInterface

if TYPE_CHECKING:
    from xtr_security_core.authentication.token.storage.token_storage_interface import (
        TokenStorageInterface,
    )
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.user.user_interface import UserInterface

    from .access_decision import AccessDecision
    from .access_decision_manager_interface import AccessDecisionManagerInterface

__all__ = ["AuthorizationChecker"]

#: The tokens :meth:`AuthorizationChecker.is_granted_for_user` is deciding for on
#: the current task, innermost last, each paired with the checker that pushed
#: it. A context variable rather than a list on the checker, so two tasks
#: sharing one checker never see each other's token.
_token_stack: ContextVar[tuple[tuple[AuthorizationChecker, TokenInterface], ...]] = ContextVar(
    "xtr_security_authorization_token_stack",
    default=(),
)


@final
class _OfflineToken(AbstractToken, OfflineTokenInterface):
    """The token :meth:`AuthorizationChecker.is_granted_for_user` decides against."""

    __slots__ = ()


class AuthorizationChecker(AuthorizationCheckerInterface, GuestAuthorizationCheckerInterface):
    """The main authorization point: answers for the current token, or for a given user.

    :meth:`is_granted` reads the token from the storage — the anonymous
    :class:`~xtr_security_core.authentication.token.null_token.NullToken` when
    none is set, or when the one set carries no user.
    :meth:`is_granted_for_user` steps outside the current caller: it builds an
    offline token — an
    :class:`~xtr_security_core.authentication.token.offline_token_interface.OfflineTokenInterface`
    — from the user's own roles, or none for a guest, and decides against that.
    Any question asked of this checker while that decision runs, by a voter
    that has the checker injected, is decided against the same offline token.
    """

    __slots__: tuple[str, ...] = ("_access_decision_manager", "_token_storage")

    _token_storage: TokenStorageInterface
    _access_decision_manager: AccessDecisionManagerInterface

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
        token = self._current_offline_token()
        if token is None:
            token = self._token_storage.get_token()
            if token is None or token.get_user() is None:
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
        user: UserInterface | None,
        attribute: object,
        subject: object = None,
        access_decision: AccessDecision | None = None,
    ) -> bool:
        """Tell whether ``user`` — or a guest, for ``None`` — may have ``attribute``."""
        token = _OfflineToken(user.get_roles() if user is not None else ())
        if user is not None:
            token.set_user(user)
        reset_token = _token_stack.set((*_token_stack.get(), (self, token)))
        try:
            return await self.is_granted(attribute, subject, access_decision)
        finally:
            _token_stack.reset(reset_token)

    def _current_offline_token(self) -> TokenInterface | None:
        """Return the innermost token this checker is deciding a given user for, if any."""
        for checker, token in reversed(_token_stack.get()):
            if checker is self:
                return token
        return None

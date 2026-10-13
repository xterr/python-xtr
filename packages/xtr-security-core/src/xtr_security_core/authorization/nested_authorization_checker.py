"""Decides each check a closure makes in a decision of its own."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_core.exception import UnsupportedUserError

from .access_decision import AccessDecision
from .authorization_checker_interface import AuthorizationCheckerInterface
from .guest_authorization_checker_interface import GuestAuthorizationCheckerInterface
from .voter.access import Access

if TYPE_CHECKING:
    from xtr_security_core.user.user_interface import UserInterface

    from .voter.vote import Vote

__all__ = ["NestedAuthorizationChecker"]


@final
class NestedAuthorizationChecker(AuthorizationCheckerInterface, GuestAuthorizationCheckerInterface):
    """Decides each check a closure makes in a decision of its own.

    The voter running the closure then knows which checks a re-authentication
    could grant, and reports the reasons they gave. One is built per closure
    run; it is an implementation detail of the closure voter.
    """

    __slots__ = ("_authorization_checker", "_re_authentication_attribute", "_votes")

    def __init__(self, authorization_checker: AuthorizationCheckerInterface) -> None:
        """Wrap the checker each nested check is decided by."""
        self._authorization_checker = authorization_checker
        self._re_authentication_attribute: str | None = None
        self._votes: list[Vote] = []

    @property
    def re_authentication_attribute(self) -> str | None:
        """The first checked attribute whose denial requested a re-authentication."""
        return self._re_authentication_attribute

    @override
    async def is_granted(
        self,
        attribute: object,
        subject: object = None,
        access_decision: AccessDecision | None = None,
    ) -> bool:
        """Decide ``attribute`` in a decision of its own, recording its votes."""
        if access_decision is not None:
            return await self._authorization_checker.is_granted(attribute, subject, access_decision)

        access_decision = AccessDecision()
        is_granted = await self._authorization_checker.is_granted(
            attribute, subject, access_decision
        )
        self._votes.extend(access_decision.votes)

        if is_granted:
            return True

        # Like the firewall does, only the voter of the checked attribute can
        # request a re-authentication for it.
        for vote in access_decision.votes:
            if (
                vote.result is Access.DENIED
                and isinstance(attribute, str)
                and attribute == vote.re_authentication_attribute
                and self._re_authentication_attribute is None
            ):
                self._re_authentication_attribute = attribute

        return False

    @override
    async def is_granted_for_user(
        self,
        user: UserInterface | None,
        attribute: object,
        subject: object = None,
        access_decision: AccessDecision | None = None,
    ) -> bool:
        """Delegate to the wrapped checker when it can decide for a given user.

        Raises:
            UnsupportedUserError: When the wrapped checker cannot check the
                access of another user.
        """
        checker = self._authorization_checker
        if not isinstance(checker, GuestAuthorizationCheckerInterface):
            raise UnsupportedUserError(
                f'"{type(checker).__qualname__}" cannot check the access of another user.',
            )
        return await checker.is_granted_for_user(user, attribute, subject, access_decision)

    def add_reasons(self, vote: Vote, is_granted: bool) -> None:
        """Add to ``vote`` the reasons the checks gave for the same outcome."""
        result = Access.GRANTED if is_granted else Access.DENIED
        for check_vote in self._votes:
            if check_vote.result is not result:
                continue
            for reason in check_vote.reasons:
                vote.add_reason(reason)

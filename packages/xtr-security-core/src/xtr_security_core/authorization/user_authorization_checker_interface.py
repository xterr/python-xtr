"""What answers "may this user do this?" without needing the current caller."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_security_core.user.user_interface import UserInterface

    from .access_decision import AccessDecision

__all__ = ["UserAuthorizationCheckerInterface"]


@runtime_checkable
class UserAuthorizationCheckerInterface(Protocol):
    """Checks the authorization of a given user, without needing a session.

    For the questions asked about someone other than the caller: a consent
    screen deciding what the user being consented-for may do, a worker deciding
    for the account a job belongs to.
    """

    async def is_granted_for_user(
        self,
        user: UserInterface,
        attribute: object,
        subject: object = None,
        access_decision: AccessDecision | None = None,
    ) -> bool:
        """Tell whether ``user`` may have ``attribute`` over ``subject``.

        Args:
            user: The user to decide for.
            attribute: A single attribute to vote on.
            subject: The subject the attribute concerns, or ``None``.
            access_decision: A record explaining the decision, if given.
        """
        ...

"""What answers "may this user do this?" for a user who is not the current caller."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_security_core.user.user_interface import UserInterface

    from .access_decision import AccessDecision

__all__ = ["GuestAuthorizationCheckerInterface"]


@runtime_checkable
class GuestAuthorizationCheckerInterface(Protocol):
    """Decides an attribute against a given user rather than the current token.

    For the questions asked about someone other than the caller: a consent
    screen deciding what the user being consented-for may do, a worker deciding
    for the account a job belongs to. It builds a throwaway token from the
    user's own roles and decides against that.
    """

    async def is_granted_for_user(
        self,
        user: UserInterface,
        attribute: object,
        subject: object = None,
        access_decision: AccessDecision | None = None,
    ) -> bool:
        """Tell whether ``user`` may have ``attribute`` over ``subject``."""
        ...

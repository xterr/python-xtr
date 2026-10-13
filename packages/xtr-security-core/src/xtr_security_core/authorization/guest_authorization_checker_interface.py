"""What answers "may this user — or a guest — do this?" for someone other than the caller."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from typing_extensions import override

from .user_authorization_checker_interface import UserAuthorizationCheckerInterface

if TYPE_CHECKING:
    from xtr_security_core.user.user_interface import UserInterface

    from .access_decision import AccessDecision

__all__ = ["GuestAuthorizationCheckerInterface"]


@runtime_checkable
class GuestAuthorizationCheckerInterface(UserAuthorizationCheckerInterface, Protocol):
    """Extends the user authorization checker with support for guests.

    A ``None`` user means a guest: the attribute is voted on with no user and
    no roles.
    """

    @override
    async def is_granted_for_user(
        self,
        user: UserInterface | None,
        attribute: object,
        subject: object = None,
        access_decision: AccessDecision | None = None,
    ) -> bool:
        """Tell whether ``user`` — or a guest, for ``None`` — may have ``attribute``.

        Args:
            user: The user to decide for, or ``None`` for a guest.
            attribute: A single attribute to vote on.
            subject: The subject the attribute concerns, or ``None``.
            access_decision: A record explaining the decision, if given.
        """
        ...

"""A passport whose user was already authenticated, carrying no credentials."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_security_http.authenticator.passport.badge.pre_authenticated_user_badge import (
    PreAuthenticatedUserBadge,
)

from .passport import Passport

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from .badge.badge_interface import BadgeInterface
    from .badge.user_badge import UserBadge

__all__ = ["SelfValidatingPassport"]


@final
class SelfValidatingPassport(Passport):
    """A passport for a user proven before it was built.

    A bearer token was verified by its handler, so there are no credentials to
    check — only the user it names. Every self-validating passport carries a
    :class:`~xtr_security_http.authenticator.passport.badge.pre_authenticated_user_badge.PreAuthenticatedUserBadge`,
    which is resolved from the start, so the passport check has nothing to
    verify and settles on the user the token proved.
    """

    def __init__(
        self,
        user_badge: UserBadge,
        badges: Iterable[BadgeInterface] = (),
        attributes: Mapping[str, object] | None = None,
    ) -> None:
        """Record the user badge, add the pre-authenticated badge, keep the rest."""
        super().__init__(user_badge, badges, attributes)
        if not self.has_badge(PreAuthenticatedUserBadge):
            _ = self.add_badge(PreAuthenticatedUserBadge())

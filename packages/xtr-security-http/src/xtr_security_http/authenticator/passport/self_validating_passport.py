"""A passport whose user was already authenticated, carrying no credentials."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from .passport import Passport

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from xtr_security_core.user.user_interface import UserInterface

    from .badge.badge_interface import BadgeInterface
    from .badge.user_badge import UserBadge

__all__ = ["SelfValidatingPassport"]


@final
class SelfValidatingPassport(Passport):
    """A passport for a user proven before it was built.

    A bearer token was verified by its handler, so there are no credentials to
    check — only the user it names. The passport check still runs: the account
    checks apply, and a badge the authenticator did not resolve still fails
    it. A
    :class:`~xtr_security_http.authenticator.passport.badge.pre_authenticated_user_badge.PreAuthenticatedUserBadge`
    is attached only by an authenticator that pre-authenticated the user
    itself — never here, or the account checks would be silently skipped for
    every self-validating authentication.
    """

    def __init__(  # pyright: ignore[reportMissingSuperCall]  # the parent constructor requires a credential; this passport exists because there is none
        self,
        user_badge: UserBadge,
        badges: Iterable[BadgeInterface] = (),
        attributes: Mapping[str, object] | None = None,
    ) -> None:
        """Record the user badge and any other badges, keyed by their class.

        The parent constructor requires a credential to verify; this passport
        exists because there is none, so the badge bookkeeping is done here
        rather than through it.
        """
        # The same slots the parent constructor would fill, minus the
        # credential this passport does not carry.
        self._badges: dict[type, BadgeInterface] = {}
        self._user: UserInterface | None = None
        _ = self.add_badge(user_badge)
        for badge in badges:
            _ = self.add_badge(badge)
        self._attributes: dict[str, object] = dict(attributes) if attributes is not None else {}

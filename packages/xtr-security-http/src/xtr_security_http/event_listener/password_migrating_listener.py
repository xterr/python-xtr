"""The listener that re-stores a verified password under the current hash."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import anyio.to_thread
from typing_extensions import override
from xtr_event_dispatcher import EventSubscriberInterface
from xtr_password_hasher import PasswordAuthenticatedUserInterface
from xtr_security_core.user.password_upgrader_interface import PasswordUpgraderInterface

from xtr_security_http.authenticator.passport.badge.password_upgrade_badge import (
    PasswordUpgradeBadge,
)
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.event.login_success_event import LoginSuccessEvent

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_event_dispatcher import SubscribedEvents
    from xtr_logging_contracts import LoggerInterface
    from xtr_password_hasher import UserPasswordHasherInterface

    from xtr_security_http.authenticator.passport.passport import Passport

__all__ = ["PasswordMigratingListener"]


@final
class PasswordMigratingListener(EventSubscriberInterface):
    """Rehashes and re-stores a password whose old hash the login verified.

    A successful password login left a
    :class:`~xtr_security_http.authenticator.passport.badge.password_upgrade_badge.PasswordUpgradeBadge`
    on the passport. This listener checks whether the stored hash is
    outdated and, when it is, rehashes the plaintext with the current
    algorithm in a worker thread and hands the new hash to an upgrader to
    store. The upgrader is whichever answers first: the one the badge
    carries, the one injected here, or — when the passport's user loader is
    a provider's bound method and that provider upgrades passwords — that
    provider. The upgrade is best-effort — it runs after the caller is
    already authenticated — so a failure is swallowed, and the hash is
    upgraded on the next login instead.
    """

    __slots__ = ("_hasher", "_logger", "_password_upgrader")

    def __init__(
        self,
        hasher: UserPasswordHasherInterface,
        password_upgrader: PasswordUpgraderInterface | None = None,
        logger: LoggerInterface | None = None,
    ) -> None:
        """Record the hasher, the upgrader used when a badge carries none, and a logger."""
        self._hasher = hasher
        self._password_upgrader = password_upgrader
        self._logger = logger

    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        """Listen to a successful, stored login."""
        return {LoginSuccessEvent: "on_login_success"}

    async def on_login_success(self, event: LoginSuccessEvent) -> None:
        """Rehash the flagged password and store it through an upgrader."""
        passport = event.get_passport()
        badge = passport.get_badge(PasswordUpgradeBadge)
        if badge is None:
            return
        plaintext = badge.get_and_erase_plaintext_password()
        if not plaintext:
            return
        user = await passport.get_user()
        if not isinstance(user, PasswordAuthenticatedUserInterface) or user.get_password() is None:
            return
        upgrader = (
            badge.get_password_upgrader()
            or self._password_upgrader
            or self._derive_upgrader(passport)
        )
        if upgrader is None:
            return
        try:
            if not await anyio.to_thread.run_sync(self._hasher.needs_rehash, user):
                return
            new_hash = await anyio.to_thread.run_sync(self._hasher.hash_password, user, plaintext)
            await upgrader.upgrade_password(user, new_hash)
        except Exception:  # noqa: BLE001 -- an opportunistic upgrade must never fail the login
            if self._logger is not None:
                self._logger.warning("Could not upgrade the password hash after a login.", {})

    def _derive_upgrader(self, passport: Passport) -> PasswordUpgraderInterface | None:
        """Read the upgrader off the user loader a provider listener bound, if it is one.

        The provider listener sets the badge's loader to the provider's bound
        ``load_user_by_identifier``, so the object the loader is bound to is
        the provider — and a provider that also implements the upgrader
        interface is where the fresh hash is written.
        """
        user_badge = passport.get_badge(UserBadge)
        if user_badge is None:
            return None
        bound = getattr(user_badge.get_user_loader(), "__self__", None)
        if isinstance(bound, PasswordUpgraderInterface):
            return bound
        return None

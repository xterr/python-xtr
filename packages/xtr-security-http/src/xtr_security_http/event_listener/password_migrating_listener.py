"""The listener that re-stores a verified password under the current hash."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import anyio.to_thread
from typing_extensions import override
from xtr_event_dispatcher import EventSubscriberInterface
from xtr_password_hasher import PasswordAuthenticatedUserInterface

from xtr_security_http.authenticator.passport.badge.password_upgrade_badge import (
    PasswordUpgradeBadge,
)
from xtr_security_http.event.login_success_event import LoginSuccessEvent

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_event_dispatcher import SubscribedEvents
    from xtr_logging_contracts import LoggerInterface
    from xtr_password_hasher import UserPasswordHasherInterface
    from xtr_security_core.user.password_upgrader_interface import PasswordUpgraderInterface

__all__ = ["PasswordMigratingListener"]


@final
class PasswordMigratingListener(EventSubscriberInterface):
    """Rehashes and re-stores a password whose old hash the login flagged as outdated.

    A successful login that verified against an outdated hash left a
    :class:`~xtr_security_http.authenticator.passport.badge.password_upgrade_badge.PasswordUpgradeBadge`
    on the passport. This listener rehashes the plaintext with the current
    algorithm in a worker thread and hands the new hash to an upgrader to
    store. The upgrade is best-effort — it runs after the caller is already
    authenticated — so a failure is swallowed, and the hash is upgraded on the
    next login instead.
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
        badge = event.get_passport().get_badge(PasswordUpgradeBadge)
        if badge is None:
            return
        plaintext = badge.get_and_erase_plaintext_password()
        if not plaintext:
            return
        upgrader = badge.get_password_upgrader() or self._password_upgrader
        if upgrader is None:
            return
        user = event.get_authenticated_token().get_user()
        if not isinstance(user, PasswordAuthenticatedUserInterface):
            return
        try:
            new_hash = await anyio.to_thread.run_sync(self._hasher.hash_password, user, plaintext)
            await upgrader.upgrade_password(user, new_hash)
        except Exception:  # noqa: BLE001 -- an opportunistic upgrade must never fail the login
            if self._logger is not None:
                self._logger.warning("Could not upgrade the password hash after a login.", {})

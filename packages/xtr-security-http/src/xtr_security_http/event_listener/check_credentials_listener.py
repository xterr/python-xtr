"""The listener that verifies a passport's credentials."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import anyio.to_thread
from typing_extensions import override
from xtr_event_dispatcher import EventSubscriberInterface
from xtr_password_hasher import PasswordAuthenticatedUserInterface
from xtr_security_core.exception import BadCredentialsError, UserNotFoundError

from xtr_security_http.authenticator.passport.badge.password_upgrade_badge import (
    PasswordUpgradeBadge,
)
from xtr_security_http.authenticator.passport.credentials.custom_credentials import (
    CustomCredentials,
)
from xtr_security_http.authenticator.passport.credentials.password_credentials import (
    PasswordCredentials,
)
from xtr_security_http.event.check_passport_event import CheckPassportEvent

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_event_dispatcher import SubscribedEvents
    from xtr_password_hasher import PasswordHasherInterface, UserPasswordHasherInterface

__all__ = ["PRIORITY", "RESOLVE_PRIORITY", "CheckCredentialsListener"]

#: The priority the credentials check runs at — after the account pre-check.
PRIORITY = 128

#: The priority the unknown-user resolve runs at — before the account pre-check.
#: Above :data:`~xtr_security_http.event_listener.user_checker_listener.PRE_PRIORITY`
#: (256) and below
#: :data:`~xtr_security_http.event_listener.user_provider_listener.PRIORITY` (2048),
#: so the badge already has its loader and the dummy is burned here, where the user
#: is first resolved, rather than letting a ``UserNotFoundError`` escape the account
#: pre-check uncharged.
RESOLVE_PRIORITY = 512

#: The throwaway plaintext hashed once, so a burn is a constant-time verify.
_DUMMY_PLAINTEXT = "dummy-password-for-timing"


@final
class CheckCredentialsListener(EventSubscriberInterface):
    """Verifies the credentials a passport carries, on the passport check.

    A ``PasswordCredentials`` is verified against the user's stored hash through
    the user password hasher, run in a worker thread so the argon2 cost never
    blocks the event loop; a match that used an outdated hash adds a
    ``PasswordUpgradeBadge`` for the migrating listener. When the user is
    unknown — or known but carrying no password — a dummy hash is still verified,
    so the timing of a bad username, a passwordless user and a wrong password all
    match and none reveals which was wrong. The dummy hash is computed once at
    construction from the required dummy hasher.

    A ``CustomCredentials`` is verified by running its own check against the
    resolved user.
    """

    __slots__ = ("_dummy_hash", "_dummy_hasher", "_hasher")

    def __init__(
        self,
        hasher: UserPasswordHasherInterface,
        dummy_hasher: PasswordHasherInterface,
    ) -> None:
        """Record the user password hasher and, for the timing guard, a dummy hasher."""
        self._hasher = hasher
        self._dummy_hasher = dummy_hasher
        self._dummy_hash = dummy_hasher.hash(_DUMMY_PLAINTEXT)

    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        """Burn for an unknown user before the pre-check, verify after it."""
        return {
            CheckPassportEvent: [
                ("resolve_user", RESOLVE_PRIORITY),
                ("check_passport", PRIORITY),
            ],
        }

    async def resolve_user(self, event: CheckPassportEvent) -> None:
        """Resolve the user a password passport names, burning a dummy on no user.

        Runs before the account pre-check, which loads the user too and would
        otherwise let a ``UserNotFoundError`` escape before the credentials
        check could charge the dummy. Only a passport carrying an unresolved
        password is touched; a known user is loaded (and cached) with no burn,
        leaving the pre-check and the verify to run as before.

        Raises:
            BadCredentialsError: When no user answers the identifier, after a
                dummy has been burned so the timing matches a wrong password.
        """
        passport = event.get_passport()
        password_credentials = passport.get_badge(PasswordCredentials)
        if password_credentials is None or password_credentials.is_resolved():
            return
        try:
            _ = await passport.get_user()
        except UserNotFoundError as error:
            await self._burn_dummy(password_credentials.get_password())
            raise BadCredentialsError("The presented credentials are invalid.") from error

    async def check_passport(self, event: CheckPassportEvent) -> None:
        """Verify the password and any custom credentials the passport carries."""
        passport = event.get_passport()
        password_credentials = passport.get_badge(PasswordCredentials)
        if password_credentials is not None and not password_credentials.is_resolved():
            await self._check_password(event, password_credentials)
        custom_credentials = passport.get_badge(CustomCredentials)
        if custom_credentials is not None and not custom_credentials.is_resolved():
            user = await passport.get_user()
            if not await custom_credentials.verify(user):
                raise BadCredentialsError("The presented credentials are invalid.")

    async def _check_password(
        self,
        event: CheckPassportEvent,
        credentials: PasswordCredentials,
    ) -> None:
        """Verify the plaintext against the user's hash, burning a dummy on no user."""
        passport = event.get_passport()
        plaintext = credentials.get_password()
        try:
            user = await passport.get_user()
        except UserNotFoundError as error:
            await self._burn_dummy(plaintext)
            raise BadCredentialsError("The presented credentials are invalid.") from error
        if not isinstance(user, PasswordAuthenticatedUserInterface):
            await self._burn_dummy(plaintext)
            raise BadCredentialsError("The user carries no password to verify against.")
        if user.get_password() is None:
            await self._burn_dummy(plaintext)
            raise BadCredentialsError("The presented credentials are invalid.")
        valid = await anyio.to_thread.run_sync(self._hasher.is_password_valid, user, plaintext)
        if not valid:
            raise BadCredentialsError("The presented credentials are invalid.")
        credentials.mark_resolved()
        if await anyio.to_thread.run_sync(self._hasher.needs_rehash, user):
            _ = passport.add_badge(PasswordUpgradeBadge(plaintext))

    async def _burn_dummy(self, plaintext: str) -> None:
        """Verify a throwaway hash, so an unknown user costs the same as a wrong password."""
        _ = await anyio.to_thread.run_sync(self._dummy_hasher.verify, self._dummy_hash, plaintext)

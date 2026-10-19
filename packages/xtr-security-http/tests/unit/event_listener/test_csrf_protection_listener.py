"""The csrf protection listener settles the passport's forgery token badge."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from xtr_event_dispatcher import EventDispatcher
from xtr_http_foundation import MemorySessionStorage, Session
from xtr_http_kernel.bridge import ResponseFactory
from xtr_password_hasher import PlaintextPasswordHasher
from xtr_security_core import TokenStorage
from xtr_security_core.exception import (
    AuthenticationError,
    BadCredentialsError,
    UserNotFoundError,
)
from xtr_security_core.user.in_memory_user import InMemoryUser
from xtr_security_csrf import CsrfToken, CsrfTokenManager, SessionTokenStorage

from tests.support.http import FakeAccessTokenHandler
from xtr_security_http.access_token.header_access_token_extractor import (
    HeaderAccessTokenExtractor,
)
from xtr_security_http.authentication.authenticator_manager import AuthenticatorManager
from xtr_security_http.authenticator.access_token_authenticator import (
    AccessTokenAuthenticator,
)
from xtr_security_http.authenticator.passport.badge.csrf_token_badge import CsrfTokenBadge
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.credentials.password_credentials import (
    PasswordCredentials,
)
from xtr_security_http.authenticator.passport.passport import Passport
from xtr_security_http.event.check_passport_event import CheckPassportEvent
from xtr_security_http.event_listener.check_credentials_listener import (
    RESOLVE_PRIORITY as USER_RESOLVE_PRIORITY,
)
from xtr_security_http.event_listener.check_credentials_listener import (
    CheckCredentialsListener,
)
from xtr_security_http.event_listener.csrf_protection_listener import (
    PRIORITY,
    CsrfProtectionListener,
)
from xtr_security_http.exception import InvalidCsrfTokenError

if TYPE_CHECKING:
    from xtr_password_hasher import PasswordAuthenticatedUserInterface

pytestmark = pytest.mark.anyio


def _csrf_manager() -> CsrfTokenManager:
    """Build a real manager over a session storage, as a firewall wires one."""
    return CsrfTokenManager(SessionTokenStorage(Session(MemorySessionStorage())))


def _event(passport: Passport) -> CheckPassportEvent:
    """Build the passport-check event a dispatcher would carry."""
    authenticator = AccessTokenAuthenticator(
        FakeAccessTokenHandler({}),
        HeaderAccessTokenExtractor(),
        ResponseFactory(),
    )
    return CheckPassportEvent(authenticator, passport)


def _passport(badge: CsrfTokenBadge | None = None) -> Passport:
    """Build a passport whose credentials are already settled."""
    credentials = PasswordCredentials("secret")
    credentials.mark_resolved()
    badges = [badge] if badge is not None else []
    return Passport(UserBadge("alice", user_loader=InMemoryUser), credentials, badges)


async def test_it_settles_the_badge_for_a_token_the_manager_vouches_for() -> None:
    manager = _csrf_manager()
    minted = await manager.get_token("authenticate")
    badge = CsrfTokenBadge("authenticate", minted.get_value())
    passport = _passport(badge)

    await CsrfProtectionListener(manager).check_passport(_event(passport))

    assert badge.is_resolved() is True


async def test_it_rejects_a_value_the_manager_does_not_vouch_for() -> None:
    manager = _csrf_manager()
    _ = await manager.get_token("authenticate")
    badge = CsrfTokenBadge("authenticate", "forged")
    passport = _passport(badge)

    with pytest.raises(InvalidCsrfTokenError):
        await CsrfProtectionListener(manager).check_passport(_event(passport))

    assert badge.is_resolved() is False


async def test_it_rejects_a_request_that_presented_no_value() -> None:
    manager = _csrf_manager()
    _ = await manager.get_token("authenticate")
    badge = CsrfTokenBadge("authenticate", None)
    passport = _passport(badge)

    with pytest.raises(InvalidCsrfTokenError):
        await CsrfProtectionListener(manager).check_passport(_event(passport))

    assert badge.is_resolved() is False


async def test_it_leaves_a_passport_with_no_badge_alone() -> None:
    manager = _RecordingManager()
    passport = _passport()

    await CsrfProtectionListener(manager).check_passport(_event(passport))

    assert manager.asked == []


async def test_it_leaves_an_already_settled_badge_alone() -> None:
    manager = _RecordingManager()
    badge = CsrfTokenBadge("authenticate", "anything")
    badge.mark_resolved()
    passport = _passport(badge)

    await CsrfProtectionListener(manager).check_passport(_event(passport))

    assert manager.asked == []


def test_it_subscribes_beside_the_user_resolve_at_priority_512() -> None:
    assert PRIORITY == 512
    assert PRIORITY == USER_RESOLVE_PRIORITY
    assert CsrfProtectionListener.get_subscribed_events() == {
        CheckPassportEvent: ("check_passport", PRIORITY),
    }


async def test_it_runs_before_the_user_resolve_at_the_shared_priority() -> None:
    """A forged request is refused before any user is loaded.

    The two listeners share priority 512, and the dispatcher runs same-priority
    listeners in registration order: registered first, the forgery check
    answers for the request — the unknown user's dummy burn never runs, and
    the failure the manager reports is the forgery, not bad credentials.
    """
    manager = _csrf_manager()
    _ = await manager.get_token("authenticate")
    dispatcher = EventDispatcher()
    dispatcher.add_subscriber(CsrfProtectionListener(manager))
    dummy = _SpyHasher()
    dispatcher.add_subscriber(CheckCredentialsListener(_UserHasher(), dummy))

    def unknown_loader(identifier: str) -> InMemoryUser:
        raise UserNotFoundError(user_identifier=identifier)

    credentials = PasswordCredentials("secret")
    passport = Passport(
        UserBadge("ghost", user_loader=unknown_loader),
        credentials,
        [CsrfTokenBadge("authenticate", "forged")],
    )
    with pytest.raises(InvalidCsrfTokenError):
        _ = await dispatcher.dispatch(_event(passport))

    assert dummy.verify_calls == 0


async def test_an_unresolved_badge_fails_the_passport_check() -> None:
    manager = _csrf_manager()
    _ = await manager.get_token("authenticate")
    passport = _passport(CsrfTokenBadge("authenticate", "forged"))

    with pytest.raises(BadCredentialsError, match="CsrfTokenBadge"):
        AuthenticatorManager(
            [
                AccessTokenAuthenticator(
                    FakeAccessTokenHandler({}),
                    HeaderAccessTokenExtractor(),
                    ResponseFactory(),
                ),
            ],
            TokenStorage(),
            EventDispatcher(),
            "api",
        )._ensure_resolved(passport)


async def test_a_badge_the_listener_settled_passes_the_passport_check() -> None:
    manager = _csrf_manager()
    minted = await manager.get_token("authenticate")
    passport = _passport(CsrfTokenBadge("authenticate", minted.get_value()))

    await CsrfProtectionListener(manager).check_passport(_event(passport))

    # No raise: every badge the passport carries is settled.
    AuthenticatorManager(
        [
            AccessTokenAuthenticator(
                FakeAccessTokenHandler({}),
                HeaderAccessTokenExtractor(),
                ResponseFactory(),
            ),
        ],
        TokenStorage(),
        EventDispatcher(),
        "api",
    )._ensure_resolved(passport)


def test_the_failure_is_an_authentication_error_never_a_missing_credential() -> None:
    """The refusal is a real failure, not a lazy authenticator's no-credential."""
    assert issubclass(InvalidCsrfTokenError, AuthenticationError)
    assert not issubclass(InvalidCsrfTokenError, BadCredentialsError)
    assert InvalidCsrfTokenError.MESSAGE_KEY == "Invalid CSRF token."


@final
class _RecordingManager:
    """A token manager that records what it was asked, and vouches for nothing."""

    __slots__ = ("asked",)

    def __init__(self) -> None:
        self.asked: list[CsrfToken] = []

    async def get_token(self, token_id: str) -> CsrfToken:
        """Mint a token; the listener never mints."""
        return CsrfToken(token_id, "minted")

    async def refresh_token(self, token_id: str) -> CsrfToken:
        """Mint a fresh value; the listener never refreshes."""
        return CsrfToken(token_id, "refreshed")

    async def remove_token(self, token_id: str) -> str | None:
        """Drop the token; the listener never removes."""
        del token_id
        return None

    async def is_token_valid(self, token: CsrfToken) -> bool:
        """Record the ask, and vouch for nothing."""
        self.asked.append(token)
        return False


@final
class _UserHasher:
    """A user password hasher over the plaintext one, as the wiring builds."""

    def __init__(self) -> None:
        self._hasher = PlaintextPasswordHasher()

    def hash_password(self, user: PasswordAuthenticatedUserInterface, plain_password: str) -> str:
        del user
        return self._hasher.hash(plain_password)

    def is_password_valid(
        self, user: PasswordAuthenticatedUserInterface, plain_password: str
    ) -> bool:
        stored = user.get_password()
        return stored is not None and self._hasher.verify(stored, plain_password)

    def needs_rehash(self, user: PasswordAuthenticatedUserInterface) -> bool:
        del user
        return False


@final
class _SpyHasher:
    """A dummy hasher that counts how often its hash and verify are burned."""

    def __init__(self) -> None:
        self._inner = PlaintextPasswordHasher()
        self.hash_calls = 0
        self.verify_calls = 0

    def hash(self, plain_password: str) -> str:
        self.hash_calls += 1
        return self._inner.hash(plain_password)

    def verify(self, hashed_password: str, plain_password: str) -> bool:
        self.verify_calls += 1
        return self._inner.verify(hashed_password, plain_password)

    def needs_rehash(self, hashed_password: str) -> bool:
        return self._inner.needs_rehash(hashed_password)

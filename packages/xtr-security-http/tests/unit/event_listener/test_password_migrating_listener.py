"""The password-migrating listener rehashes and stores on login success."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override
from xtr_event_dispatcher import EventDispatcher
from xtr_http_kernel.bridge import ResponseFactory
from xtr_password_hasher import PlaintextPasswordHasher
from xtr_security_core.exception import UserNotFoundError
from xtr_security_core.user.in_memory_user import InMemoryUser
from xtr_security_core.user.in_memory_user_provider import InMemoryUserProvider
from xtr_security_core.user.password_upgrader_interface import PasswordUpgraderInterface
from xtr_security_core.user.user_provider_interface import UserProviderInterface

from tests.support.http import FakeAccessTokenHandler
from tests.support.messages import make_message
from xtr_security_http.access_token.header_access_token_extractor import HeaderAccessTokenExtractor
from xtr_security_http.authenticator.access_token_authenticator import AccessTokenAuthenticator
from xtr_security_http.authenticator.passport.badge.password_upgrade_badge import (
    PasswordUpgradeBadge,
)
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.credentials.password_credentials import (
    PasswordCredentials,
)
from xtr_security_http.authenticator.passport.passport import Passport
from xtr_security_http.authenticator.token.post_authentication_token import PostAuthenticationToken
from xtr_security_http.event.check_passport_event import CheckPassportEvent
from xtr_security_http.event.login_success_event import LoginSuccessEvent
from xtr_security_http.event_listener.check_credentials_listener import CheckCredentialsListener
from xtr_security_http.event_listener.password_migrating_listener import PasswordMigratingListener
from xtr_security_http.event_listener.user_provider_listener import UserProviderListener

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from xtr_password_hasher import PasswordAuthenticatedUserInterface
    from xtr_security_core.user.user_interface import UserInterface

pytestmark = pytest.mark.anyio

#: The plaintext every fixture user's stored password was made from.
_PLAINTEXT = "secret"


@final
class _UserHasher:
    """Hashes under a ``rehashed:`` prefix and reports rehash need as configured."""

    def __init__(self, *, needs_rehash: bool = True) -> None:
        self._needs_rehash = needs_rehash
        self.hash_calls = 0

    def hash_password(self, user: PasswordAuthenticatedUserInterface, plain_password: str) -> str:
        del user
        self.hash_calls += 1
        return f"rehashed:{plain_password}"

    def is_password_valid(
        self, user: PasswordAuthenticatedUserInterface, plain_password: str
    ) -> bool:
        stored = user.get_password()
        return stored is not None and stored in (plain_password, f"rehashed:{plain_password}")

    def needs_rehash(self, user: PasswordAuthenticatedUserInterface) -> bool:
        del user
        return self._needs_rehash


@final
class _UpgradingProvider(UserProviderInterface, PasswordUpgraderInterface):
    """Loads one user and records every hash it is asked to store."""

    def __init__(self, user: InMemoryUser) -> None:
        self._user = user
        self.stored_hashes: list[str] = []

    @override
    async def load_user_by_identifier(self, identifier: str) -> UserInterface:
        if identifier != self._user.get_user_identifier():
            raise UserNotFoundError(user_identifier=identifier)
        return self._user

    @override
    async def refresh_user(self, user: UserInterface) -> UserInterface:
        return user

    @override
    def supports_class(self, user_class: type) -> bool:
        return issubclass(user_class, InMemoryUser)

    @override
    async def upgrade_password(
        self,
        user: PasswordAuthenticatedUserInterface,
        new_hashed_password: str,
    ) -> None:
        del user
        self.stored_hashes.append(new_hashed_password)


@final
class _RecordingUpgrader(PasswordUpgraderInterface):
    """Records the one hash it is asked to store."""

    def __init__(self) -> None:
        self.stored: str | None = None

    @override
    async def upgrade_password(
        self,
        user: PasswordAuthenticatedUserInterface,
        new_hashed_password: str,
    ) -> None:
        del user
        self.stored = new_hashed_password


def _authenticator() -> AccessTokenAuthenticator:
    return AccessTokenAuthenticator(
        FakeAccessTokenHandler({}),
        HeaderAccessTokenExtractor(),
        ResponseFactory(),
    )


def _token() -> PostAuthenticationToken:
    return PostAuthenticationToken(InMemoryUser("alice"), "api", ())


def _login_success_event(passport: Passport) -> LoginSuccessEvent:
    return LoginSuccessEvent(_authenticator(), passport, _token(), make_message(), None, "api")


def _passport_with_loader(
    loader: Callable[[str], UserInterface | Awaitable[UserInterface]],
) -> Passport:
    return Passport(UserBadge("alice", user_loader=loader), PasswordCredentials(_PLAINTEXT))


def _passport_with_password_user() -> Passport:
    return _passport_with_loader(
        lambda identifier: InMemoryUser(identifier, password=_PLAINTEXT),
    )


async def test_it_rehashes_and_stores() -> None:
    upgrader = _RecordingUpgrader()
    passport = _passport_with_password_user()
    _ = passport.add_badge(PasswordUpgradeBadge(_PLAINTEXT, upgrader))

    await PasswordMigratingListener(_UserHasher()).on_login_success(
        _login_success_event(passport),
    )

    assert upgrader.stored == f"rehashed:{_PLAINTEXT}"


async def test_it_does_nothing_without_a_badge() -> None:
    passport = _passport_with_password_user()
    hasher = _UserHasher()

    await PasswordMigratingListener(hasher).on_login_success(_login_success_event(passport))

    assert hasher.hash_calls == 0


async def test_it_derives_the_upgrader_from_the_user_loader() -> None:
    provider = _UpgradingProvider(InMemoryUser("alice", password=_PLAINTEXT))
    passport = _passport_with_loader(provider.load_user_by_identifier)
    _ = passport.add_badge(PasswordUpgradeBadge(_PLAINTEXT))
    hasher = _UserHasher()

    await PasswordMigratingListener(hasher).on_login_success(_login_success_event(passport))

    assert provider.stored_hashes == [f"rehashed:{_PLAINTEXT}"]
    assert hasher.hash_calls == 1


async def test_it_stays_off_when_the_provider_is_not_an_upgrader() -> None:
    provider = InMemoryUserProvider(
        {"alice": {"password": _PLAINTEXT, "roles": [], "enabled": True}}
    )
    passport = _passport_with_loader(provider.load_user_by_identifier)
    _ = passport.add_badge(PasswordUpgradeBadge(_PLAINTEXT))
    hasher = _UserHasher()

    await PasswordMigratingListener(hasher).on_login_success(_login_success_event(passport))

    assert hasher.hash_calls == 0


async def test_the_injected_upgrader_runs_when_the_badge_has_none() -> None:
    upgrader = _RecordingUpgrader()
    passport = _passport_with_password_user()
    _ = passport.add_badge(PasswordUpgradeBadge(_PLAINTEXT))

    await PasswordMigratingListener(_UserHasher(), password_upgrader=upgrader).on_login_success(
        _login_success_event(passport),
    )

    assert upgrader.stored == f"rehashed:{_PLAINTEXT}"


async def test_it_skips_the_upgrade_when_no_rehash_is_needed() -> None:
    upgrader = _RecordingUpgrader()
    passport = _passport_with_password_user()
    _ = passport.add_badge(PasswordUpgradeBadge(_PLAINTEXT, upgrader))
    hasher = _UserHasher(needs_rehash=False)

    await PasswordMigratingListener(hasher).on_login_success(_login_success_event(passport))

    assert upgrader.stored is None
    assert hasher.hash_calls == 0


def _passwordless(identifier: str) -> InMemoryUser:
    """Load a user with no stored password, taking the identifier alone.

    The badge would hand a two-argument loader its attributes as well, and the
    in-memory user's second argument is its password — so the loader here
    takes the identifier only.
    """
    return InMemoryUser(identifier)


async def test_it_skips_a_user_with_no_stored_password() -> None:
    upgrader = _RecordingUpgrader()
    passport = _passport_with_loader(_passwordless)
    _ = passport.add_badge(PasswordUpgradeBadge(_PLAINTEXT, upgrader))
    hasher = _UserHasher()

    await PasswordMigratingListener(hasher).on_login_success(_login_success_event(passport))

    assert upgrader.stored is None
    assert hasher.hash_calls == 0


async def test_the_password_is_upgraded_end_to_end_through_the_listeners() -> None:
    provider = _UpgradingProvider(InMemoryUser("alice", password=_PLAINTEXT))
    dispatcher = EventDispatcher()
    dispatcher.add_subscriber(UserProviderListener(provider))
    dispatcher.add_subscriber(CheckCredentialsListener(_UserHasher(), PlaintextPasswordHasher()))
    dispatcher.add_subscriber(PasswordMigratingListener(_UserHasher()))

    passport = Passport(UserBadge("alice"), PasswordCredentials(_PLAINTEXT))
    _ = await dispatcher.dispatch(CheckPassportEvent(_authenticator(), passport))
    _ = await dispatcher.dispatch(_login_success_event(passport))

    assert provider.stored_hashes == [f"rehashed:{_PLAINTEXT}"]

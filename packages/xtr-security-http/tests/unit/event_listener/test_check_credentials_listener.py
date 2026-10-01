"""The check-credentials listener verifies credentials and flags rehashing."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from xtr_password_hasher import PlaintextPasswordHasher
from xtr_security_core.exception import BadCredentialsError
from xtr_security_core.user.in_memory_user import InMemoryUser

from tests.support.http import FakeAccessTokenHandler
from tests.support.users import accept, loader, reject
from xtr_security_http.access_token.header_access_token_extractor import HeaderAccessTokenExtractor
from xtr_security_http.authenticator.access_token_authenticator import AccessTokenAuthenticator
from xtr_security_http.authenticator.passport.badge.password_upgrade_badge import (
    PasswordUpgradeBadge,
)
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.credentials.custom_credentials import (
    CustomCredentials,
)
from xtr_security_http.authenticator.passport.credentials.password_credentials import (
    PasswordCredentials,
)
from xtr_security_http.authenticator.passport.passport import Passport
from xtr_security_http.event.check_passport_event import CheckPassportEvent
from xtr_security_http.event_listener.check_credentials_listener import CheckCredentialsListener

if TYPE_CHECKING:
    from xtr_password_hasher import PasswordAuthenticatedUserInterface

pytestmark = pytest.mark.anyio


def _event(passport: Passport) -> CheckPassportEvent:
    authenticator = AccessTokenAuthenticator(
        FakeAccessTokenHandler({}), HeaderAccessTokenExtractor()
    )
    return CheckPassportEvent(authenticator, passport)


@final
class _UserHasher:
    def __init__(self, *, needs_rehash: bool = False) -> None:
        self._hasher = PlaintextPasswordHasher()
        self._needs_rehash = needs_rehash

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
        return self._needs_rehash


async def test_it_verifies_a_password() -> None:
    hasher = _UserHasher()
    stored = hasher.hash_password(InMemoryUser("alice"), "secret")
    passport = Passport(
        UserBadge("alice", user_loader=loader(password=stored)),
        [PasswordCredentials("secret")],
    )

    await CheckCredentialsListener(hasher).check_passport(_event(passport))

    credentials = passport.get_badge(PasswordCredentials)
    assert credentials is not None
    assert credentials.is_resolved() is True


async def test_it_rejects_a_wrong_password() -> None:
    hasher = _UserHasher()
    stored = hasher.hash_password(InMemoryUser("alice"), "secret")
    passport = Passport(
        UserBadge("alice", user_loader=loader(password=stored)),
        [PasswordCredentials("wrong")],
    )

    with pytest.raises(BadCredentialsError):
        await CheckCredentialsListener(hasher).check_passport(_event(passport))


async def test_it_adds_an_upgrade_badge_when_rehash_is_needed() -> None:
    hasher = _UserHasher(needs_rehash=True)
    stored = hasher.hash_password(InMemoryUser("alice"), "secret")
    passport = Passport(
        UserBadge("alice", user_loader=loader(password=stored)),
        [PasswordCredentials("secret")],
    )

    await CheckCredentialsListener(hasher).check_passport(_event(passport))

    assert passport.has_badge(PasswordUpgradeBadge) is True


async def test_it_burns_a_dummy_for_an_unknown_user() -> None:
    from xtr_security_core.exception import UserNotFoundError  # noqa: PLC0415

    def unknown_loader(identifier: str) -> InMemoryUser:
        raise UserNotFoundError(user_identifier=identifier)

    passport = Passport(
        UserBadge("ghost", user_loader=unknown_loader),
        [PasswordCredentials("secret")],
    )
    dummy = _SpyHasher()

    with pytest.raises(BadCredentialsError):
        await CheckCredentialsListener(_UserHasher(), dummy).check_passport(_event(passport))

    assert dummy.verify_calls == 1


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


@final
class _PasswordlessUser:
    """A user that carries no password — not a password-authenticated user."""

    def get_roles(self) -> list[str]:
        return ["ROLE_USER"]

    def get_user_identifier(self) -> str:
        return "machine"


async def test_it_burns_a_dummy_when_the_user_has_no_password() -> None:
    def load_passwordless(identifier: str) -> _PasswordlessUser:
        del identifier
        return _PasswordlessUser()

    passport = Passport(
        UserBadge("machine", user_loader=load_passwordless),
        [PasswordCredentials("secret")],
    )
    dummy = _SpyHasher()

    with pytest.raises(BadCredentialsError):
        await CheckCredentialsListener(_UserHasher(), dummy).check_passport(_event(passport))

    assert dummy.verify_calls == 1


async def test_it_runs_custom_credentials() -> None:
    passport = Passport(
        UserBadge("alice", user_loader=InMemoryUser),
        [CustomCredentials(accept, "ok")],
    )

    await CheckCredentialsListener(_UserHasher()).check_passport(_event(passport))

    custom = passport.get_badge(CustomCredentials)
    assert custom is not None
    assert custom.is_resolved() is True


async def test_it_rejects_bad_custom_credentials() -> None:
    passport = Passport(
        UserBadge("alice", user_loader=InMemoryUser),
        [CustomCredentials(reject, "x")],
    )

    with pytest.raises(BadCredentialsError):
        await CheckCredentialsListener(_UserHasher()).check_passport(_event(passport))


async def test_resolve_user_burns_a_dummy_before_the_account_check() -> None:
    from xtr_security_core.exception import UserNotFoundError  # noqa: PLC0415

    def unknown_loader(identifier: str) -> InMemoryUser:
        raise UserNotFoundError(user_identifier=identifier)

    passport = Passport(
        UserBadge("ghost", user_loader=unknown_loader),
        [PasswordCredentials("secret")],
    )
    dummy = _SpyHasher()

    with pytest.raises(BadCredentialsError):
        await CheckCredentialsListener(_UserHasher(), dummy).resolve_user(_event(passport))

    assert dummy.verify_calls == 1


async def test_resolve_user_loads_a_known_user_without_burning() -> None:
    hasher = _UserHasher()
    stored = hasher.hash_password(InMemoryUser("alice"), "secret")
    passport = Passport(
        UserBadge("alice", user_loader=loader(password=stored)),
        [PasswordCredentials("secret")],
    )
    dummy = _SpyHasher()

    await CheckCredentialsListener(hasher, dummy).resolve_user(_event(passport))

    assert dummy.verify_calls == 0
    credentials = passport.get_badge(PasswordCredentials)
    assert credentials is not None
    assert credentials.is_resolved() is False


async def test_resolve_user_ignores_a_passport_with_no_password() -> None:
    passport = Passport(
        UserBadge("alice", user_loader=InMemoryUser),
        [CustomCredentials(accept, "ok")],
    )
    dummy = _SpyHasher()

    await CheckCredentialsListener(_UserHasher(), dummy).resolve_user(_event(passport))

    assert dummy.verify_calls == 0


async def test_the_dummy_hash_is_computed_eagerly_at_construction() -> None:
    dummy = _SpyHasher()

    _ = CheckCredentialsListener(_UserHasher(), dummy)

    assert dummy.hash_calls == 1

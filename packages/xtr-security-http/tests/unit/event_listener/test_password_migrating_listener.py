"""The password-migrating listener rehashes and stores on login success."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override
from xtr_password_hasher import PlaintextPasswordHasher
from xtr_security_core.user.in_memory_user import InMemoryUser
from xtr_security_core.user.password_upgrader_interface import PasswordUpgraderInterface

from tests.support.http import FakeAccessTokenHandler
from tests.support.requests import make_request
from xtr_security_http.access_token.header_access_token_extractor import HeaderAccessTokenExtractor
from xtr_security_http.authenticator.access_token_authenticator import AccessTokenAuthenticator
from xtr_security_http.authenticator.passport.badge.password_upgrade_badge import (
    PasswordUpgradeBadge,
)
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.passport import Passport
from xtr_security_http.authenticator.token.post_authentication_token import PostAuthenticationToken
from xtr_security_http.event.login_success_event import LoginSuccessEvent
from xtr_security_http.event_listener.password_migrating_listener import PasswordMigratingListener

if TYPE_CHECKING:
    from xtr_password_hasher import PasswordAuthenticatedUserInterface

pytestmark = pytest.mark.anyio


@final
class _UserHasher:
    def hash_password(self, user: PasswordAuthenticatedUserInterface, plain: str) -> str:
        del user
        return PlaintextPasswordHasher().hash(plain)

    def is_password_valid(self, user: PasswordAuthenticatedUserInterface, plain: str) -> bool:
        stored = user.get_password()
        return stored is not None and PlaintextPasswordHasher().verify(stored, plain)

    def needs_rehash(self, user: PasswordAuthenticatedUserInterface) -> bool:
        del user
        return False


@final
class _RecordingUpgrader(PasswordUpgraderInterface):
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


def _login_success_event(passport: Passport, token: PostAuthenticationToken) -> LoginSuccessEvent:
    authenticator = AccessTokenAuthenticator(
        FakeAccessTokenHandler({}), HeaderAccessTokenExtractor()
    )
    return LoginSuccessEvent(authenticator, passport, token, make_request(), None, "api")


async def test_it_rehashes_and_stores() -> None:
    upgrader = _RecordingUpgrader()
    passport = Passport(UserBadge("alice"))
    _ = passport.add_badge(PasswordUpgradeBadge("secret", upgrader))
    token = PostAuthenticationToken(InMemoryUser("alice", password="old"), "api", ())  # noqa: S106
    event = _login_success_event(passport, token)

    await PasswordMigratingListener(_UserHasher()).on_login_success(event)

    assert upgrader.stored is not None


async def test_it_does_nothing_without_a_badge() -> None:
    passport = Passport(UserBadge("alice"))
    token = PostAuthenticationToken(InMemoryUser("alice"), "api", ())
    event = _login_success_event(passport, token)

    await PasswordMigratingListener(_UserHasher()).on_login_success(event)

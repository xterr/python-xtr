"""The wired listeners derive the password upgrader from the provider.

Boots the migration fixture — an upgrading provider over one in-memory user
whose stored hash is a legacy PBKDF2 one, behind a migrating argon2id hasher —
and drives a password login's listener chain through the firewall's real
dispatcher, so the derivation the wiring leaves to the passport is proven
end to end: the provider listener binds the provider's method as the user
loader, the credentials check verifies and flags the password, and the
migrating listener rehashes and hands the new hash back to the provider.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from xtr_dependency_injection import Kernel, unit_of_work
from xtr_dependency_injection.testing import boot_for_test
from xtr_event_dispatcher_contracts import EventDispatcherInterface
from xtr_http_kernel.bridge import ResponseFactory
from xtr_password_hasher import UserPasswordHasherInterface
from xtr_security_core import InMemoryUser
from xtr_security_core.user.user_provider_interface import UserProviderInterface
from xtr_security_http.access_token.header_access_token_extractor import HeaderAccessTokenExtractor
from xtr_security_http.authenticator.access_token_authenticator import AccessTokenAuthenticator
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.credentials.password_credentials import (
    PasswordCredentials,
)
from xtr_security_http.authenticator.passport.passport import Passport
from xtr_security_http.authenticator.token.post_authentication_token import (
    PostAuthenticationToken,
)
from xtr_security_http.event.check_passport_event import CheckPassportEvent
from xtr_security_http.event.login_success_event import LoginSuccessEvent
from xtr_security_http.exception import InvalidAccessTokenError

from tests.fixtures.migration_app.services import PLAINTEXT, STORED_HASH, UpgradingUserProvider
from tests.support.messages import make_message
from xtr_security.bundle import SecurityBundle, firewall_dispatcher_name

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from xtr_service_contracts import ContainerInterface

pytestmark = pytest.mark.anyio


@final
class _NoTokensHandler:
    """Rejects every token; the login event only carries the authenticator."""

    __slots__ = ()

    async def get_user_badge_from(self, access_token: str) -> UserBadge:
        """Reject the token.

        Raises:
            InvalidAccessTokenError: Always; no token opens this fixture.
        """
        del access_token
        raise InvalidAccessTokenError("The token is not known.")


@pytest.fixture
async def container() -> AsyncIterator[ContainerInterface]:
    kernel = Kernel(
        "tests.fixtures.migration_app",
        env="test",
        bundles={SecurityBundle: {"all": True}},
        concurrent_scoped_access=True,
    )
    async with await boot_for_test(kernel) as booted:
        yield booted.container


def _authenticator() -> AccessTokenAuthenticator:
    return AccessTokenAuthenticator(
        _NoTokensHandler(),
        HeaderAccessTokenExtractor(),
        ResponseFactory(),
    )


async def test_the_wired_listeners_upgrade_the_password_through_the_provider(
    container: ContainerInterface,
) -> None:
    async with unit_of_work(container) as unit:
        dispatcher = await unit.get(EventDispatcherInterface, firewall_dispatcher_name("api"))
        passport = Passport(UserBadge("alice"), PasswordCredentials(PLAINTEXT))
        _ = await dispatcher.dispatch(CheckPassportEvent(_authenticator(), passport))
        token = PostAuthenticationToken(await passport.get_user(), "api", ())
        _ = await dispatcher.dispatch(
            LoginSuccessEvent(_authenticator(), passport, token, make_message(), None, "api"),
        )
        provider = await unit.get(UserProviderInterface, "users")
        hasher = await unit.get(UserPasswordHasherInterface)

    assert isinstance(provider, UpgradingUserProvider)
    (upgraded,) = provider.stored_hashes
    assert upgraded != STORED_HASH
    assert hasher.is_password_valid(InMemoryUser("alice", password=upgraded), PLAINTEXT)

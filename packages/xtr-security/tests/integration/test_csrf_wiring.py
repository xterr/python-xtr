"""The forgery-token wiring, over a real container: the manager, the listeners, the seams.

Boots the CSRF fixture — a stateful firewall with a form login whose form
carries a token, and a logout that demands one and drops the stored ones —
and reads back what the bundle registered: the request's token manager the
route marker's checker survives on, the passport check's listener ahead of
the user load, the logout's proof and its clearing, and the session strategy
holding the storage a migration empties.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

import pytest
from xtr_dependency_injection import Kernel, unit_of_work
from xtr_dependency_injection.testing import boot_for_test
from xtr_event_dispatcher import EventDispatcher, LazyListener
from xtr_event_dispatcher_contracts import EventDispatcherInterface
from xtr_security_core import TokenInterface
from xtr_security_csrf.csrf_token_manager import CsrfTokenManager
from xtr_security_csrf.csrf_token_manager_interface import CsrfTokenManagerInterface
from xtr_security_csrf.token_storage.session_token_storage import SessionTokenStorage
from xtr_security_http import CheckPassportEvent, CsrfTokenChecker, LogoutEvent
from xtr_security_http.authenticator.authenticator_interface import AuthenticatorInterface
from xtr_security_http.authenticator.passport.badge.csrf_token_badge import CsrfTokenBadge
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.credentials.password_credentials import (
    PasswordCredentials,
)
from xtr_security_http.authenticator.passport.passport import Passport
from xtr_security_http.event.login_success_event import LoginSuccessEvent
from xtr_security_http.event_listener.check_credentials_listener import (
    CheckCredentialsListener,
)
from xtr_security_http.exception.invalid_csrf_token_error import InvalidCsrfTokenError
from xtr_security_http.firewall.logout_listener import LogoutListener
from xtr_security_http.session.session_authentication_strategy import (
    SessionAuthenticationStrategy,
)

from tests.support.messages import make_message
from tests.support.sessions import request_parking_a_session
from xtr_security.bundle import SecurityBundle, firewall_dispatcher_name
from xtr_security.bundle._csrf_wiring import ParkedRequest, ParkedSessionTokenStorage
from xtr_security.bundle.firewall_context import FirewallContext

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from xtr_service_contracts import ContainerInterface

pytestmark = pytest.mark.anyio


@pytest.fixture
async def container() -> AsyncIterator[ContainerInterface]:
    """Boot the CSRF fixture the way the kernel boots an application."""
    kernel = Kernel(
        "tests.fixtures.csrf_app",
        env="test",
        bundles={SecurityBundle: {"all": True}},
        concurrent_scoped_access=True,
    )
    async with await boot_for_test(kernel) as booted:
        yield booted.container


async def _listeners_of(unit: ContainerInterface, dispatcher: str, event: type) -> list[object]:
    """Return the dispatcher's listeners of ``event``, lazy ones resolved to their owners."""
    resolved = cast(
        "EventDispatcher",
        await unit.get(EventDispatcherInterface, firewall_dispatcher_name(dispatcher)),
    )
    listeners = [
        await listener.resolve() if isinstance(listener, LazyListener) else listener
        for listener in resolved.get_listeners(event)
    ]
    return [getattr(listener, "__self__", listener) for listener in listeners]


async def test_the_manager_answers_as_the_interface_the_checker_watches(
    container: ContainerInterface,
) -> None:
    """The manager's arrival is what keeps the route marker's checker alive."""
    async with unit_of_work(container) as unit:
        manager = await unit.get(CsrfTokenManagerInterface)
        checker = await unit.get(CsrfTokenChecker)

    assert isinstance(manager, CsrfTokenManager)
    assert isinstance(checker, CsrfTokenChecker)


async def test_the_passport_check_runs_the_forgery_check_ahead_of_the_user_load(
    container: ContainerInterface,
) -> None:
    """The forged request is refused before any user is loaded.

    The check and the resolve step share the priority 512, and the dispatcher
    runs same-priority listeners in the order they were registered: the
    per-call listener the bundle places runs first.
    """
    async with unit_of_work(container) as unit:
        listeners = await _listeners_of(unit, "main", CheckPassportEvent)

    names = [getattr(listener, "__name__", type(listener).__name__) for listener in listeners]
    # The helper collapses a bound method to its owner, so the credentials
    # listener's first appearance is its resolve step — the other 512 the
    # forgery check must run ahead of.
    assert names.index("check_the_passport_token") < names.index("CheckCredentialsListener"), (
        "the forgery check must refuse a forged request before any user is loaded"
    )
    assert any(isinstance(listener, CheckCredentialsListener) for listener in listeners)


async def test_the_logout_step_proves_the_request_and_the_event_clears_the_tokens(
    container: ContainerInterface,
) -> None:
    async with unit_of_work(container) as unit:
        context = await unit.get(FirewallContext, "main")
        listeners = await _listeners_of(unit, "main", LogoutEvent)

    logout = cast("LogoutListener", context.logout_listener)
    assert isinstance(logout._csrf_token_manager, CsrfTokenManager)
    names = [getattr(listener, "__name__", type(listener).__name__) for listener in listeners]
    assert "clear_csrf_tokens_on_logout" in names


async def test_the_session_strategy_holds_the_clearable_storage(
    container: ContainerInterface,
) -> None:
    async with unit_of_work(container) as unit:
        strategy = await unit.get(
            SessionAuthenticationStrategy, "main#session_authentication_strategy"
        )

    assert isinstance(
        strategy._csrf_token_storage,
        ParkedSessionTokenStorage,
    )


async def test_the_passport_check_settles_a_badge_through_the_per_call_manager(
    container: ContainerInterface,
) -> None:
    """A badge the manager vouches for settles; one it does not fails the check.

    The dispatch runs the per-call listener the pass placed, resolving the
    request's own manager through the real dispatcher — the mechanism the
    wiring exists for, driven the way the chain drives it.
    """
    async with unit_of_work(container) as unit:
        request_park = await unit.get(ParkedRequest)
        request, session = request_parking_a_session()
        request_park.request = request
        await SessionTokenStorage(session).set_token("authenticate", "a-value")
        dispatcher = await unit.get(EventDispatcherInterface, firewall_dispatcher_name("main"))

        settled = _passport_with(CsrfTokenBadge("authenticate", "a-value"))
        _ = await dispatcher.dispatch(
            CheckPassportEvent(
                cast("AuthenticatorInterface", cast("object", _NoAuthenticator())),
                settled,
                None,
            )
        )
        settled_badge = settled.get_badge(CsrfTokenBadge)
        assert settled_badge is not None
        assert settled_badge.is_resolved()

        refused = _passport_with(CsrfTokenBadge("authenticate", "forged"))
        with pytest.raises(InvalidCsrfTokenError):
            _ = await dispatcher.dispatch(
                CheckPassportEvent(
                    cast("AuthenticatorInterface", cast("object", _NoAuthenticator())),
                    refused,
                    None,
                )
            )


async def test_a_login_success_runs_the_strategy_through_the_per_call_listener(
    container: ContainerInterface,
) -> None:
    """The strategy listener the pass placed answers a login the chain announces.

    The event carries a request no stateful machinery ran for, so the
    strategy skips it — the pin is that the per-call listener resolved the
    firewall's strategy and handed it the login without raising. The shared
    password-migrating listener answers the same dispatch, so the event
    carries the passport it reads.
    """
    async with unit_of_work(container) as unit:
        dispatcher = await unit.get(EventDispatcherInterface, firewall_dispatcher_name("main"))
        _ = await dispatcher.dispatch(
            LoginSuccessEvent(
                cast("AuthenticatorInterface", cast("object", _NoAuthenticator())),
                _passport_with(None),
                cast("TokenInterface", cast("object", None)),
                make_message(),
                None,
                "main",
            ),
        )


@final
class _NoAuthenticator:
    """The event's authenticator, unread by the check this drives."""

    __slots__ = ()


def _passport_with(badge: CsrfTokenBadge | None) -> Passport:
    """Build a passport whose credentials are already settled, carrying ``badge``."""
    credentials = PasswordCredentials("secret")
    credentials.mark_resolved()
    badges = [badge] if badge is not None else []
    return Passport(UserBadge("alice"), credentials, badges)

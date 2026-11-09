"""The listeners a firewall runs over the user: its load, its account checks, its cookie.

A dispatcher keeps its listeners for the application's life, so a listener
service must be a singleton — and a singleton cannot hold what belongs to one
request. The firewall's user provider, its user checker and its remember-me
handler may be exactly that: a provider reading users through the session of
the request's unit of work is one of the request's services. These listeners
are functions instead, placed into the firewall's dispatcher by
:class:`~xtr_security.bundle.RegisterPerCallListenersPass`: the container
fills their injected parameters on every call, from the unit of work the
request opened, so the provider the passport check loads a user through is
the one the request's authenticator holds. Each wraps the landed listener
class it answers for, built for the call, and is named plainly — its
qualified name is its name — so the dispatcher's listings read it alone.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast

from xtr_dependency_injection import Autowire, Target
from xtr_security_core import InMemoryUserChecker
from xtr_security_core.event.authentication_success_event import AuthenticationSuccessEvent
from xtr_security_core.user.user_provider_interface import UserProviderInterface
from xtr_security_http import (
    CheckPassportEvent,
    LoginFailureEvent,
    LoginSuccessEvent,
    LogoutEvent,
    RememberMeListener,
    TokenDeauthenticatedEvent,
    UserCheckerListener,
    UserProviderListener,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from xtr_security_core.user.user_checker_interface import UserCheckerInterface
    from xtr_security_http import RememberMeHandlerInterface

__all__ = [
    "account_post_check_listener",
    "account_pre_check_listener",
    "remember_me_clearing_listener",
    "remember_me_login_listener",
    "user_loading_listener",
]


def user_loading_listener(provider_qualifier: str) -> Callable[..., Awaitable[None]]:
    """Return the passport-check listener giving a badge its loader from the firewall's provider.

    The provider is the firewall's own, named by its qualifier, so the
    listener is built per firewall: the closure carries the qualifier into
    the annotation the container reads.
    """

    async def load_the_user(event: CheckPassportEvent, provider: object) -> None:
        await UserProviderListener(cast("UserProviderInterface", provider)).check_passport(event)

    load_the_user.__annotations__ = {
        "event": CheckPassportEvent,
        "provider": Annotated[UserProviderInterface, Target(provider_qualifier)],
        "return": None,
    }
    load_the_user.__qualname__ = load_the_user.__name__
    return load_the_user


def account_pre_check_listener(user_checker: type | None) -> Callable[..., Awaitable[None]]:
    """Return the passport-check listener running the account's pre-authentication check.

    Without a checker configured, the in-memory checker the security core
    ships — stateless, so one serves every call.
    """
    default = InMemoryUserChecker()

    async def check_the_account_before_credentials(
        event: CheckPassportEvent,
        checker: object | None = None,
    ) -> None:
        resolved = cast("UserCheckerInterface", checker if checker is not None else default)
        await UserCheckerListener(resolved).pre_check_credentials(event)

    check_the_account_before_credentials.__annotations__ = _checker_annotations(
        CheckPassportEvent, user_checker
    )
    check_the_account_before_credentials.__qualname__ = (
        check_the_account_before_credentials.__name__
    )
    return check_the_account_before_credentials


def account_post_check_listener(user_checker: type | None) -> Callable[..., Awaitable[None]]:
    """Return the success listener running the account's post-authentication check.

    Without a checker configured, the in-memory checker the security core
    ships — stateless, so one serves every call.
    """
    default = InMemoryUserChecker()

    async def check_the_account_after_login(
        event: AuthenticationSuccessEvent,
        checker: object | None = None,
    ) -> None:
        resolved = cast("UserCheckerInterface", checker if checker is not None else default)
        await UserCheckerListener(resolved).post_check_credentials(event)

    check_the_account_after_login.__annotations__ = _checker_annotations(
        AuthenticationSuccessEvent, user_checker
    )
    check_the_account_after_login.__qualname__ = check_the_account_after_login.__name__
    return check_the_account_after_login


def remember_me_login_listener(
    handler_type: type,
    handler_qualifier: str,
) -> Callable[..., Awaitable[None]]:
    """Return the login-success listener setting the cookie a remembered login earned."""

    async def remember_the_login(event: LoginSuccessEvent, handler: object) -> None:
        await RememberMeListener(cast("RememberMeHandlerInterface", handler)).on_login_success(
            event
        )

    remember_the_login.__annotations__ = {
        "event": LoginSuccessEvent,
        "handler": Annotated[handler_type, Target(handler_qualifier)],  # ty: ignore[invalid-type-form] -- runtime marker
        "return": None,
    }
    remember_the_login.__qualname__ = remember_the_login.__name__
    return remember_the_login


def remember_me_clearing_listener(
    handler_type: type,
    handler_qualifier: str,
) -> Callable[..., Awaitable[None]]:
    """Return the listener clearing the cookie on an ending that must not leave a login kept."""

    async def forget_the_login(
        event: LoginFailureEvent | LogoutEvent | TokenDeauthenticatedEvent,
        handler: object,
    ) -> None:
        await RememberMeListener(cast("RememberMeHandlerInterface", handler)).clear_cookie(event)

    forget_the_login.__annotations__ = {
        "event": LoginFailureEvent | LogoutEvent | TokenDeauthenticatedEvent,
        "handler": Annotated[handler_type, Target(handler_qualifier)],  # ty: ignore[invalid-type-form] -- runtime marker
        "return": None,
    }
    forget_the_login.__qualname__ = forget_the_login.__name__
    return forget_the_login


def _checker_annotations(event: type, user_checker: type | None) -> dict[str, object]:
    """Return an account check's annotations, injecting the checker only when one is configured.

    The container fills only a marked parameter of a function it binds, so
    the configured checker is marked; with none, the parameter stays
    unmarked and keeps its ``None`` default.
    """
    annotations: dict[str, object] = {"event": event, "return": None}
    if user_checker is not None:
        annotations["checker"] = Annotated[user_checker, Autowire()]  # ty: ignore[invalid-type-form] -- runtime marker
    return annotations

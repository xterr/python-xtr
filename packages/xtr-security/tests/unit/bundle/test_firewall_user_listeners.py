"""The per-call listeners a firewall runs over its user, built from their factories."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast, final

import pytest
from xtr_dependency_injection import Autowire, Target
from xtr_security_core.event.authentication_success_event import AuthenticationSuccessEvent
from xtr_security_core.exception import DisabledError
from xtr_security_core.user.in_memory_user import InMemoryUser
from xtr_security_core.user.user_provider_interface import UserProviderInterface
from xtr_security_http import (
    CheckPassportEvent,
    LoginSuccessEvent,
    LogoutEvent,
    SignatureRememberMeHandler,
)
from xtr_security_http.authenticator.passport.badge.pre_authenticated_user_badge import (
    PreAuthenticatedUserBadge,
)
from xtr_security_http.authenticator.passport.badge.remember_me_badge import RememberMeBadge
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.self_validating_passport import (
    SelfValidatingPassport,
)
from xtr_security_http.authenticator.token.post_authentication_token import (
    PostAuthenticationToken,
)

from tests.support.messages import make_message
from xtr_security.bundle._firewall_user_listeners import (
    account_post_check_listener,
    account_pre_check_listener,
    remember_me_clearing_listener,
    remember_me_login_listener,
    user_loading_listener,
)

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.user.user_interface import UserInterface
    from xtr_security_http.authenticator.authenticator_interface import AuthenticatorInterface
    from xtr_security_http.authenticator.passport.passport import Passport

pytestmark = pytest.mark.anyio

_AUTHENTICATOR = cast("AuthenticatorInterface", object())


@final
class _Provider:
    """A provider answering every identifier with an in-memory user."""

    __slots__ = ()

    async def load_user_by_identifier(self, identifier: str) -> UserInterface:
        return InMemoryUser(identifier)

    async def refresh_user(self, user: UserInterface) -> UserInterface:
        return user

    def supports_class(self, user_class: type) -> bool:
        del user_class
        return True


@final
class _Checker:
    """A checker recording the checks it was asked to run."""

    __slots__ = ("calls",)

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def check_pre_auth(self, user: UserInterface) -> None:
        self.calls.append(f"pre:{user.get_user_identifier()}")

    async def check_post_auth(self, user: UserInterface, token: TokenInterface) -> None:
        del token
        self.calls.append(f"post:{user.get_user_identifier()}")


@final
class _Handler:
    """A remember-me handler recording what it was asked to stage."""

    __slots__ = ("calls",)

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def create_remember_me_cookie(
        self, request: ServerRequestInterface, user: UserInterface
    ) -> None:
        del request
        self.calls.append(f"create:{user.get_user_identifier()}")

    async def clear_remember_me_cookie(self, request: ServerRequestInterface) -> None:
        del request
        self.calls.append("clear")


def _passport_check(passport: Passport) -> CheckPassportEvent:
    return CheckPassportEvent(_AUTHENTICATOR, passport)


def _token(identifier: str = "alice") -> PostAuthenticationToken:
    return PostAuthenticationToken(InMemoryUser(identifier), "main", ())


def _disabled(identifier: str) -> InMemoryUser:
    return InMemoryUser(identifier, enabled=False)


async def test_the_user_loading_listener_gives_a_loaderless_badge_the_providers_loader() -> None:
    badge = UserBadge("alice")
    provider = _Provider()

    await user_loading_listener("users")(
        _passport_check(SelfValidatingPassport(badge)), provider=provider
    )

    loader = badge.get_user_loader()
    assert loader is not None
    assert getattr(loader, "__self__", None) is provider


async def test_the_user_loading_listener_leaves_a_badge_with_a_loader_alone() -> None:
    badge = UserBadge("alice", user_loader=InMemoryUser)

    await user_loading_listener("users")(
        _passport_check(SelfValidatingPassport(badge)), provider=_Provider()
    )

    assert badge.get_user_loader() is InMemoryUser


def test_the_user_loading_listener_targets_the_firewalls_provider() -> None:
    listener = user_loading_listener("users")

    assert listener.__annotations__["provider"] == Annotated[UserProviderInterface, Target("users")]


async def test_the_account_pre_check_runs_the_configured_checker() -> None:
    checker = _Checker()
    passport = SelfValidatingPassport(UserBadge("alice", user_loader=InMemoryUser))

    await account_pre_check_listener(_Checker)(_passport_check(passport), checker=checker)

    assert checker.calls == ["pre:alice"]


async def test_the_account_pre_check_skips_a_pre_authenticated_passport() -> None:
    checker = _Checker()
    passport = SelfValidatingPassport(
        UserBadge("alice", user_loader=InMemoryUser), [PreAuthenticatedUserBadge()]
    )

    await account_pre_check_listener(_Checker)(_passport_check(passport), checker=checker)

    assert checker.calls == []


async def test_the_account_post_check_runs_the_configured_checker() -> None:
    checker = _Checker()

    await account_post_check_listener(_Checker)(
        AuthenticationSuccessEvent(_token()), checker=checker
    )

    assert checker.calls == ["post:alice"]


async def test_without_a_configured_checker_the_account_checks_use_the_in_memory_checker() -> None:
    disabled = SelfValidatingPassport(UserBadge("alice", user_loader=_disabled))

    with pytest.raises(DisabledError):
        await account_pre_check_listener(None)(_passport_check(disabled))


def test_a_configured_checker_is_injected_and_none_is_not() -> None:
    configured = account_pre_check_listener(_Checker).__annotations__
    unconfigured = account_post_check_listener(None).__annotations__

    assert configured["checker"] == Annotated[_Checker, Autowire()]
    assert "checker" not in unconfigured


async def test_remembering_a_login_goes_through_the_firewalls_handler() -> None:
    handler = _Handler()
    passport = SelfValidatingPassport(
        UserBadge("alice", user_loader=InMemoryUser), [RememberMeBadge().enable()]
    )
    _ = await passport.get_user()  # the passport check loaded it, as on a real login
    event = LoginSuccessEvent(_AUTHENTICATOR, passport, _token(), make_message(), None, "main")

    await remember_me_login_listener(SignatureRememberMeHandler, "main#remember_me_handler")(
        event, handler=handler
    )

    assert handler.calls == ["clear", "create:alice"]


async def test_forgetting_a_login_goes_through_the_firewalls_handler() -> None:
    handler = _Handler()

    await remember_me_clearing_listener(SignatureRememberMeHandler, "main#remember_me_handler")(
        LogoutEvent(make_message(), None), handler=handler
    )

    assert handler.calls == ["clear"]


def test_each_listener_is_named_plainly() -> None:
    listeners = (
        user_loading_listener("users"),
        account_pre_check_listener(None),
        account_post_check_listener(None),
        remember_me_login_listener(SignatureRememberMeHandler, "q"),
        remember_me_clearing_listener(SignatureRememberMeHandler, "q"),
    )

    assert [getattr(listener, "__qualname__", "") for listener in listeners] == [
        "load_the_user",
        "check_the_account_before_credentials",
        "check_the_account_after_login",
        "remember_the_login",
        "forget_the_login",
    ]

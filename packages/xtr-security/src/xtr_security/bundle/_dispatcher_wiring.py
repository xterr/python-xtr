"""A firewall's own dispatcher, and the listeners every secured firewall shares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast

from xtr_clock import ClockInterface
from xtr_dependency_injection import Target, named_factory
from xtr_event_dispatcher.bundle import DISPATCHER_TAG, SUBSCRIBER_TAG, event_dispatcher_factory
from xtr_password_hasher import (  # noqa: TC002 -- factory signatures the container reads
    PasswordHasherInterface,
    UserPasswordHasherInterface,
)
from xtr_security_core.user.user_provider_interface import UserProviderInterface
from xtr_security_http import (
    AuthenticationProofsListener,
    CheckCredentialsListener,
    PasswordMigratingListener,
)
from xtr_security_http.event_listener import UserCheckerListener, UserProviderListener

from xtr_security.bundle._hasher_wiring import DUMMY_PASSWORD_HASHER_QUALIFIER
from xtr_security.bundle.firewall_dispatcher_name import firewall_dispatcher_name

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_dependency_injection import ServiceConfigurator
    from xtr_security_core.user.user_checker_interface import UserCheckerInterface

    from xtr_security.firewall_config import FirewallConfig

__all__ = ["register_dispatcher", "register_shared_listeners"]


def register_dispatcher(
    services: ServiceConfigurator,
    name: str,
    firewall: FirewallConfig,
    provider_qualifier: str | None,
) -> None:
    """Register the firewall's own dispatcher, and the listeners only it runs.

    The event dispatcher bundle hands the dispatcher every listener naming it:
    the user provider and user checker listeners of this firewall, registered
    here. The listeners every firewall shares are on the main dispatcher, and
    reach this one through
    :class:`~xtr_security.bundle.RegisterGlobalSecurityEventListenersPass`.
    """
    dispatcher = firewall_dispatcher_name(name)
    _ = services.set(event_dispatcher_factory(dispatcher), qualifier=dispatcher).add_tag(
        DISPATCHER_TAG
    )
    if provider_qualifier is not None:
        _ = services.set(
            named_factory(
                user_provider_listener_factory(provider_qualifier), f"user_provider_listener_{name}"
            ),
            qualifier=dispatcher,
        ).add_tag(SUBSCRIBER_TAG, dispatcher=dispatcher)
    _ = services.set(
        named_factory(
            user_checker_listener_factory(firewall.user_checker), f"user_checker_listener_{name}"
        ),
        qualifier=dispatcher,
    ).add_tag(SUBSCRIBER_TAG, dispatcher=dispatcher)


def user_provider_listener_factory(
    provider_qualifier: str,
) -> Callable[..., UserProviderListener]:
    """Return the factory of the listener loading users from the firewall's provider."""

    def user_provider_listener(provider: UserProviderInterface) -> UserProviderListener:
        return UserProviderListener(provider)

    user_provider_listener.__annotations__ = {
        "provider": Annotated[UserProviderInterface, Target(provider_qualifier)],
        "return": UserProviderListener,
    }
    return user_provider_listener


def user_checker_listener_factory(
    user_checker: type | None,
) -> Callable[..., UserCheckerListener]:
    """Return the factory of the listener checking the account with the firewall's checker.

    Without one configured, the in-memory checker the security core ships.
    """

    def user_checker_listener(checker: object | None = None) -> UserCheckerListener:
        from xtr_security_core import InMemoryUserChecker  # noqa: PLC0415 -- default checker

        resolved = checker if checker is not None else InMemoryUserChecker()
        return UserCheckerListener(cast("UserCheckerInterface", resolved))

    annotations: dict[str, object] = {"return": UserCheckerListener}
    if user_checker is not None:
        annotations["checker"] = user_checker
    user_checker_listener.__annotations__ = annotations
    return user_checker_listener


def register_shared_listeners(services: ServiceConfigurator, *, clock_active: bool) -> None:
    """Register, on the main dispatcher, the listeners every secured firewall runs.

    They reach each firewall's dispatcher through
    :class:`~xtr_security.bundle.RegisterGlobalSecurityEventListenersPass`, as an
    application's own security listeners do. The proofs listener needs no
    configuration to run — only the token and the event — so it joins them
    unconditionally, stamping its records with the application's clock when
    the clock bundle is active and the system clock otherwise.
    """
    _ = services.set(check_credentials_listener).add_tag(SUBSCRIBER_TAG)
    _ = services.set(password_migrating_listener).add_tag(SUBSCRIBER_TAG)
    _ = services.set(_authentication_proofs_listener(clock_active)).add_tag(SUBSCRIBER_TAG)


def _authentication_proofs_listener(
    clock_active: bool,
) -> Callable[..., AuthenticationProofsListener]:
    """Return the factory of the listener recording what a login proved.

    The clock is injected only while the clock bundle is active — the
    trust resolver's pattern — so the listener stamps its proofs with the
    application's clock where one is configured, and the system clock
    otherwise.
    """

    def authentication_proofs_listener(clock: object | None = None) -> AuthenticationProofsListener:
        """Build the listener recording the methods a login proved."""
        return AuthenticationProofsListener(cast("ClockInterface | None", clock))

    annotations: dict[str, object] = {"return": AuthenticationProofsListener}
    if clock_active:
        annotations["clock"] = ClockInterface
    authentication_proofs_listener.__annotations__ = annotations
    return authentication_proofs_listener


def check_credentials_listener(
    hasher: UserPasswordHasherInterface,
    dummy_hasher: Annotated[PasswordHasherInterface, Target(DUMMY_PASSWORD_HASHER_QUALIFIER)],
) -> CheckCredentialsListener:
    """Build the credentials check, with the dummy hasher an unknown user's check burns."""
    return CheckCredentialsListener(hasher, dummy_hasher)


def password_migrating_listener(hasher: UserPasswordHasherInterface) -> PasswordMigratingListener:
    """Build the listener rehashing a password flagged as outdated."""
    return PasswordMigratingListener(hasher)

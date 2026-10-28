"""The listener that counts a firewall's login attempts, and refuses the rest.

A login form is where an anonymous caller may try again and again, so the
flow counts the attempts under two limiters — the address each attempt came
from, and the account each named — built over the storage the application
registered, the same storage every other limiter of the application counts
in. The counting keys are derived inside the limiter, from a secret the
application supplies: the bundle builds and boots without it, and the
listener fails naming it the first time it is asked for.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from xtr_clock import ClockInterface
from xtr_dependency_injection import Target, named_factory
from xtr_event_dispatcher.bundle import SUBSCRIBER_TAG
from xtr_event_dispatcher_contracts import EventDispatcherInterface
from xtr_rate_limiter import LimiterConfig, RateLimiterFactory
from xtr_rate_limiter.storage.storage_interface import StorageInterface
from xtr_security_http import DefaultLoginRateLimiter, LoginThrottlingListener

from xtr_security.bundle.firewall_dispatcher_name import firewall_dispatcher_name
from xtr_security.exception import InvalidConfigurationError

if TYPE_CHECKING:
    from xtr_dependency_injection import ServiceConfigurator

    from xtr_security.login_throttling_config import LoginThrottlingConfig

__all__ = ["register_login_throttling"]


def register_login_throttling(
    services: ServiceConfigurator,
    name: str,
    settings: LoginThrottlingConfig,
) -> None:
    """Register the throttling listener on the firewall's own dispatcher.

    The listener runs ahead of every other check a passport answers to —
    at ``2080``, above the provider's own ``2048`` — so a request already
    over the limit is refused before any user is loaded or any password
    verified. The two limiters it counts under are its own, built over the
    application's storage when the listener is first asked for: an
    application that registered none is told so, by name, at that moment.
    """
    dispatcher = firewall_dispatcher_name(name)

    def login_throttling_listener(
        storage: StorageInterface,
        clock: ClockInterface | None = None,
        firewall_dispatcher: EventDispatcherInterface | None = None,
    ) -> LoginThrottlingListener:
        """Build the listener counting this firewall's attempts under its two limiters."""
        if not settings.secret:
            raise InvalidConfigurationError(
                f'The login throttling of the firewall "{name}" derives its counting keys '
                f'with a "secret" the application must supply; set one on the '
                f"login-throttling configuration.",
            )
        global_factory = RateLimiterFactory(
            f"{name}#login_throttling_global",
            LimiterConfig(
                "fixed_window", limit=settings.global_limit, interval=settings.global_interval
            ),
            storage,
            clock=clock,
        )
        local_factory = RateLimiterFactory(
            f"{name}#login_throttling_local",
            LimiterConfig(
                "fixed_window", limit=settings.local_limit, interval=settings.local_interval
            ),
            storage,
            clock=clock,
        )
        return LoginThrottlingListener(
            DefaultLoginRateLimiter(global_factory, local_factory, settings.secret),
            dispatcher=firewall_dispatcher,
            clock=clock,
        )

    login_throttling_listener.__annotations__ = {
        "storage": StorageInterface,
        "clock": ClockInterface | None,
        "firewall_dispatcher": Annotated[EventDispatcherInterface, Target(dispatcher)],
        "return": LoginThrottlingListener,
    }
    login_throttling_listener.__name__ = f"login_throttling_listener_{name}"
    login_throttling_listener.__qualname__ = login_throttling_listener.__name__
    _ = services.set(
        named_factory(login_throttling_listener, f"login_throttling_listener_{name}"),
        qualifier=dispatcher,
    ).add_tag(SUBSCRIBER_TAG, dispatcher=dispatcher)

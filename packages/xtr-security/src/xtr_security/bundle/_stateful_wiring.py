"""The stateful machinery a firewall that keeps a session wires.

A stateful firewall restores the token its session carries on every request,
and rotates that session when a login succeeds — the two halves the
application's ``SessionStorageInterface`` service makes possible. The
listener carrying the token across requests is registered only while that
storage exists: the definition carries the container's remove-if-missing
marker, so an application that registered no storage is told so by the
bundle's guard pass rather than by a chain naming a listener that is not
there.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from xtr_dependency_injection import Target, named_factory
from xtr_dependency_injection.decorator.remove_if_missing import REMOVE_IF_MISSING_TAG
from xtr_event_dispatcher.bundle import SUBSCRIBER_TAG
from xtr_event_dispatcher_contracts import EventDispatcherInterface
from xtr_http_foundation import SessionStorageInterface
from xtr_security_core import (
    AuthenticationTrustResolverInterface,
    TokenStorageInterface,
)
from xtr_security_core.user.user_provider_interface import (
    UserProviderInterface,
)

from xtr_security.bundle._authenticator_wiring import register_missing_user_provider
from xtr_security.bundle.firewall_dispatcher_name import firewall_dispatcher_name

if TYPE_CHECKING:
    from xtr_dependency_injection import ServiceConfigurator, ServiceKey

    from xtr_security.firewall_config import FirewallConfig

__all__ = ["context_listener_name", "register_context_listener", "register_session_strategy"]


def context_listener_name(firewall_name: str) -> str:
    """The qualifier of a firewall's context chain listener."""
    return f"{firewall_name}#context_listener"


def _qualified(key: ServiceKey) -> object:
    """Return the injection annotation selecting the service ``key`` names.

    Built at runtime from a service key, so the second type checker reads the
    subscript as a static type expression it is not — hence the suppression;
    the container evaluates it as the marker it forms.
    """
    return Annotated[key[0], Target(key[1])]  # ty: ignore[invalid-type-form] -- runtime marker


def register_context_listener(
    services: ServiceConfigurator,
    name: str,
    firewall: FirewallConfig,
    provider_qualifier: str | None,
) -> str:
    """Register the chain step that carries an authenticated user across requests.

    The listener is parked ahead of the manager's own chain step — both sit
    at the default priority, and the gathering order runs the context first —
    so the token the session carries is restored before anything
    authenticates, and the logins the request brings are written back by the
    response half. Its definition carries the remove-if-missing marker over
    the application's session storage: with no storage registered the
    definition is dropped, and the bundle's guard pass fails the build naming
    the missing service — a firewall the application asked to be stateful
    cannot silently run as a stateless one.

    The user the session token carries is reloaded through the firewall's
    provider; a firewall naming none gets the same placeholder the
    authenticators get, which fails naming the firewall the first time it is
    asked for.
    """
    from xtr_security_http import (  # noqa: PLC0415 -- the family's chain-step import
        ContextListener,
        FirewallListenerInterface,
    )

    context_key = firewall.context_key if firewall.context_key is not None else name
    provider_key: ServiceKey = (
        (UserProviderInterface, provider_qualifier)
        if provider_qualifier is not None
        else register_missing_user_provider(services, name)
    )

    def context_listener(
        storage: TokenStorageInterface,
        provider: UserProviderInterface,
        session_storage: SessionStorageInterface,
        dispatcher: EventDispatcherInterface,
        trust_resolver: AuthenticationTrustResolverInterface,
    ) -> ContextListener:
        """Build the step over one firewall's session key and provider."""
        return ContextListener(
            storage,
            (provider,),
            context_key,
            session_storage,
            dispatcher=dispatcher,
            trust_resolver=trust_resolver,
        )

    context_listener.__annotations__ = {
        "storage": TokenStorageInterface,
        "provider": _qualified(provider_key),
        "session_storage": SessionStorageInterface,
        "dispatcher": EventDispatcherInterface,
        "trust_resolver": AuthenticationTrustResolverInterface,
        "return": ContextListener,
    }
    context_listener.__name__ = f"context_listener_{name}"
    context_listener.__qualname__ = context_listener.__name__
    qualifier = context_listener_name(name)
    definition = services.set(context_listener, qualifier=qualifier, lifetime="scoped")
    # The storage is the application's to register; the marker drops the
    # listener while it is absent, and the bundle's guard pass turns that
    # drop into a refusal naming the missing service.
    _ = definition.add_tag(REMOVE_IF_MISSING_TAG, service=SessionStorageInterface)
    services.alias(
        FirewallListenerInterface,
        ContextListener,
        alias_qualifier=qualifier,
        target_qualifier=qualifier,
    )
    return qualifier


def register_session_strategy(
    services: ServiceConfigurator,
    name: str,
    firewall: FirewallConfig,
) -> None:
    """Register what a successful login does to the session it reattached.

    The strategy itself is a service of the firewall's own, and the listener
    handing it a login runs on the firewall's own dispatcher — the same
    place its login listeners run — as a subscriber on the login-success
    event. The clearable cross-site request forgery storage a migration
    would empty is not wired yet: the strategy rotates the session's ID
    without it, and the forgery tokens minted under the old ID go with it
    once the storage joins.
    """
    from xtr_security_http import (  # noqa: PLC0415 -- the family's session import
        SessionAuthenticationStrategy,
        SessionStrategyListener,
    )

    strategy_qualifier = f"{name}#session_authentication_strategy"

    def session_authentication_strategy() -> SessionAuthenticationStrategy:
        """Build the strategy the firewall configured."""
        return SessionAuthenticationStrategy(firewall.session_strategy, None)

    session_authentication_strategy.__annotations__ = {
        "return": SessionAuthenticationStrategy,
    }
    session_authentication_strategy.__name__ = f"session_authentication_strategy_{name}"
    session_authentication_strategy.__qualname__ = session_authentication_strategy.__name__
    _ = services.set(session_authentication_strategy, qualifier=strategy_qualifier)

    def session_strategy_listener(
        strategy: SessionAuthenticationStrategy,
    ) -> SessionStrategyListener:
        """Build the listener handing the firewall's logins to the strategy."""
        return SessionStrategyListener(strategy)

    session_strategy_listener.__annotations__ = {
        "strategy": Annotated[SessionAuthenticationStrategy, Target(strategy_qualifier)],
        "return": SessionStrategyListener,
    }
    dispatcher = firewall_dispatcher_name(name)
    _ = services.set(
        named_factory(session_strategy_listener, f"session_strategy_listener_{name}"),
        qualifier=dispatcher,
    ).add_tag(SUBSCRIBER_TAG, dispatcher=dispatcher)

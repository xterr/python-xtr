"""The stateful machinery a firewall that keeps a session wires.

A stateful firewall restores the token its session carries on every request,
and rotates that session when a login succeeds — the two halves the
application's ``SessionStorageInterface`` service makes possible. The
listener carrying the token across requests is registered only while that
storage exists: the definition carries the container's remove-if-missing
marker, so an application that registered no storage is told so by the
bundle's guard pass rather than by a chain naming a listener that is not
there. The response side is wired here too: the context step's response half
stores the token back, and the save listener writes the session itself
through the storage and stages the cookie that carries its ID — without
them, nothing the chain writes to a session survives the request.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast

from xtr_dependency_injection import Target
from xtr_dependency_injection.decorator.remove_if_missing import REMOVE_IF_MISSING_TAG
from xtr_event_dispatcher.bundle import SUBSCRIBER_TAG
from xtr_event_dispatcher_contracts import EventDispatcherInterface
from xtr_http_foundation import SessionStorageInterface
from xtr_http_kernel import ResponseEvent
from xtr_security_core import (
    AuthenticationTrustResolverInterface,
    TokenStorageInterface,
)
from xtr_security_core.user.user_provider_interface import (
    UserProviderInterface,
)
from xtr_security_csrf.token_storage.clearable_token_storage_interface import (
    ClearableTokenStorageInterface,
)

from xtr_security.bundle._authenticator_wiring import register_missing_user_provider

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from xtr_dependency_injection import ServiceConfigurator, ServiceKey

    from xtr_security.firewall_config import FirewallConfig

__all__ = [
    "context_listener_name",
    "register_context_listener",
    "register_session_save_listener",
    "register_session_strategy",
    "session_authentication_strategy_name",
    "store_the_context",
]


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
    *,
    csrf_wired: bool,
) -> None:
    """Register what a successful login does to the session it reattached.

    The strategy is a service of the firewall's own, scoped like the request
    it acts on: it holds the clearable cross-site request forgery storage a
    migration empties — the request's own, over the session it reattached —
    whenever the forgery-token machinery is wired, and nothing otherwise.
    The listener handing it a login is placed by the bundle's per-call pass,
    not registered here: a dispatcher keeps its listeners for the
    application's life, and this one holds what belongs to one request.
    """
    from xtr_security_http import (  # noqa: PLC0415 -- the family's session import
        SessionAuthenticationStrategy,
    )

    strategy_qualifier = session_authentication_strategy_name(name)

    def session_authentication_strategy(
        storage: object | None = None,
    ) -> SessionAuthenticationStrategy:
        """Build the strategy the firewall configured, over the storage it clears."""
        return SessionAuthenticationStrategy(
            firewall.session_strategy,
            cast("ClearableTokenStorageInterface | None", storage),
        )

    annotations: dict[str, object] = {"return": SessionAuthenticationStrategy}
    if csrf_wired:
        annotations["storage"] = ClearableTokenStorageInterface
    session_authentication_strategy.__annotations__ = annotations

    session_authentication_strategy.__name__ = f"session_authentication_strategy_{name}"
    session_authentication_strategy.__qualname__ = session_authentication_strategy.__name__
    _ = services.set(
        session_authentication_strategy, qualifier=strategy_qualifier, lifetime="scoped"
    )


def session_authentication_strategy_name(firewall_name: str) -> str:
    """The qualifier of a firewall's session authentication strategy."""
    return f"{firewall_name}#session_authentication_strategy"


def register_session_save_listener(services: ServiceConfigurator) -> None:
    """Register the listener that writes the reattached session back out.

    One service for the application, placed on the main dispatcher: the
    session it saves is the request's own, read off the event's state, so
    nothing about it is per-firewall. It is registered only while a stateful
    firewall is configured, and its definition carries the same
    remove-if-missing marker over the application's session storage as the
    context step it serves: with no storage registered both are dropped, and
    the bundle's guard pass fails the build naming the missing service.
    """
    from xtr_security_http import (  # noqa: PLC0415 -- the family's session import
        SaveSessionListener,
    )

    definition = services.set(SaveSessionListener)
    _ = definition.add_tag(SUBSCRIBER_TAG)
    # The storage is the application's to register; the marker drops the
    # listener while it is absent, beside the context step it serves.
    _ = definition.add_tag(REMOVE_IF_MISSING_TAG, service=SessionStorageInterface)


def store_the_context(context_listener_qualifier: str) -> Callable[..., Awaitable[None]]:
    """Return the response listener storing the token through its firewall's context step.

    The context step is a service of the firewall — scoped, like the request
    it reattaches the session for — so the listener is built per firewall:
    the closure carries the qualifier into the annotation the container
    reads, and resolves the step — the request's own — on every response.
    """
    from xtr_security_http import (  # noqa: PLC0415 -- the family's chain-step import
        ContextListener,
    )

    async def store_the_token(event: ResponseEvent, context_listener: object) -> None:
        await cast("ContextListener", context_listener).on_response(event)

    store_the_token.__annotations__ = {
        "event": ResponseEvent,
        "context_listener": Annotated[ContextListener, Target(context_listener_qualifier)],
        "return": None,
    }
    return store_the_token

"""Gathering one firewall's parts into its context definition."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast

from xtr_dependency_injection import ServiceLocator, Target
from xtr_event_dispatcher_contracts import EventDispatcherInterface
from xtr_http_kernel.bridge import StarletteHttpFactoryInterface
from xtr_http_message_contracts.factory import ResponseFactoryInterface
from xtr_logging_contracts import LoggerInterface
from xtr_security_core import (
    AccessDecisionManagerInterface,
    AuthenticationTrustResolverInterface,
    TokenStorageInterface,
)
from xtr_security_http import (
    AccessListener,
    AccessMap,
    AuthenticatorManager,
    AuthenticatorManagerListener,
    ExceptionListener,
    ExposeSecurityLevel,
    FirewallListenerInterface,
    InsufficientScopeAccessDeniedHandler,
    LogoutListener,
    SenderConstraintInterface,
)
from xtr_security_http.authenticator.authenticator_interface import (
    AuthenticatorInterface,
)

from xtr_security.bundle._firewall_settings import access_token_settings_of, realm_of
from xtr_security.bundle.firewall_access_listener_name import firewall_access_listener_name
from xtr_security.bundle.firewall_context import FirewallContext
from xtr_security.bundle.firewall_dispatcher_name import firewall_dispatcher_name
from xtr_security.bundle.firewall_manager_listener_name import firewall_manager_listener_name

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_dependency_injection import ServiceConfigurator
    from xtr_security_http.authenticator.passport.badge.badge_interface import BadgeInterface
    from xtr_security_http.authorization.access_denied_handler_interface import (
        AccessDeniedHandlerInterface,
    )
    from xtr_security_http.entry_point.authentication_entry_point_interface import (
        AuthenticationEntryPointInterface,
    )

    from xtr_security.firewall_config import FirewallConfig

__all__ = ["register_context_factory"]


def register_context_factory(  # noqa: PLR0913, PLR0915, C901 -- one factory gathering one firewall's parts; each branch injects one part
    services: ServiceConfigurator,
    name: str,
    firewall: FirewallConfig,
    *,
    auth_qualifiers: tuple[str, ...],
    entry_point_qualifier: str | None,
    access_map: AccessMap,
    expose: ExposeSecurityLevel,
    extra_listeners: tuple[str, ...] = (),
    context_listener: str | None = None,
    logout_listener: str | None = None,
    channel_listener: str | None = None,
    logging_active: bool = False,
) -> None:
    """Register the factory that gathers one firewall's parts into a context.

    The authenticators are asked of a locator by the qualifiers this firewall's
    authenticators were aliased under, so a firewall builds its own and no other
    firewall's; the manager is a service of its own over them and the injected
    storage and dispatcher, so the chain's listener and the context hand each
    other the same one; the entry point is read off the built authenticators.
    ``expose`` is the configured
    :class:`~xtr_security_http.ExposeSecurityLevel`, threaded to the manager so a
    non-default level reaches every firewall.

    The manager's chain step is registered beside the context and aliased under
    :class:`~xtr_security_http.firewall.firewall_listener_interface.FirewallListenerInterface`,
    its qualifier parked ahead of the application's own listeners — so every
    secured firewall's chain carries its authentication step without the
    application naming it, and the sorting pass orders it with the rest. The
    access step is registered the same way, over the same storage and decision
    manager the runner decides with and the firewall's own access map: the
    chain's step and the context's ``access_listener`` are one service, so
    what the chain would decide is what the runner decides today. The chain is
    parked on the context definition's ``listeners`` argument — the
    P2.1 convention the sorting pass reads — so it is ordered before the
    context resolves it through the locator, in the order the pass left it.
    A stateful firewall's context step is parked ahead of the manager's own,
    so the token its session carries is restored before anything
    authenticates. The exception listener is built per firewall, from the
    firewall's own parts — its name, its resolved entry point, its configured
    denial handler, the scope handler over its realm — so a request's failure is
    answered by the firewall that ran it. The scope handler reads its RFC 9728
    ``resource_metadata`` URI and its sender constraint off the firewall's
    first access-token authenticator, and its inner handler off the firewall's
    ``scope_denied_handler`` — a fallback challenge never answers for a real
    one, and the two stay one configuration.

    ``extra_listeners`` names further chain steps the bundle itself parked —
    an OIDC login's token-refresh listener — ahead of the listeners the
    application's own configuration names; the sorting pass orders them with
    the rest. ``logout_listener`` names the logout step a configured logout
    registered: the context carries it on its own logout slot, where the
    firewall runs it at its priority instead of the chain's ordering.

    ``channel_listener`` names the channel step a firewall with channel rules
    runs: parked first on the chain, ahead of the context step and the
    manager's own, so a request arriving over the wrong scheme is redirected
    before anything it carries is spent. ``logging_active`` hands the
    exception listener the application's logger, the way the trust resolver
    takes the application's clock while the clock bundle is active.
    """
    realm = realm_of(firewall)
    scope_settings = access_token_settings_of(firewall)
    scope_resource_metadata_uri = (
        scope_settings.resource_metadata_uri if scope_settings is not None else None
    )
    scope_constraint_qualifier = (
        scope_settings.sender_constraint if scope_settings is not None else None
    )
    access_denied = firewall.access_denied_handler
    scope_denied = firewall.scope_denied_handler
    manager_qualifier = f"{name}#authenticator_manager"
    listener_qualifier = firewall_manager_listener_name(name)
    access_listener_qualifier = firewall_access_listener_name(name)

    async def authenticator_manager(
        storage: TokenStorageInterface,
        dispatcher: EventDispatcherInterface,
        authenticators: ServiceLocator[AuthenticatorInterface],
    ) -> AuthenticatorManager:
        """Build the firewall's manager over its own authenticators."""
        auths = [await authenticators.get(qualifier) for qualifier in auth_qualifiers]
        return AuthenticatorManager(
            auths,
            storage,
            dispatcher,
            name,
            expose_security_errors=expose,
            required_badges=cast("Sequence[type[BadgeInterface]]", firewall.required_badges),
        )

    authenticator_manager.__annotations__ = {
        "storage": TokenStorageInterface,
        "dispatcher": Annotated[EventDispatcherInterface, Target(firewall_dispatcher_name(name))],
        "authenticators": ServiceLocator[AuthenticatorInterface],
        "return": AuthenticatorManager,
    }
    authenticator_manager.__name__ = f"authenticator_manager_{name}"
    authenticator_manager.__qualname__ = authenticator_manager.__name__
    _ = services.set(authenticator_manager, qualifier=manager_qualifier, lifetime="scoped")

    async def authenticator_manager_listener(
        manager: AuthenticatorManager,
        bridge: StarletteHttpFactoryInterface,
    ) -> AuthenticatorManagerListener:
        """Build the chain step that runs the firewall's manager."""
        return AuthenticatorManagerListener(manager, bridge)

    authenticator_manager_listener.__annotations__ = {
        "manager": Annotated[AuthenticatorManager, Target(manager_qualifier)],
        "bridge": StarletteHttpFactoryInterface,
        "return": AuthenticatorManagerListener,
    }
    authenticator_manager_listener.__name__ = f"authenticator_manager_listener_{name}"
    authenticator_manager_listener.__qualname__ = authenticator_manager_listener.__name__
    _ = services.set(
        authenticator_manager_listener, qualifier=listener_qualifier, lifetime="scoped"
    )
    services.alias(
        FirewallListenerInterface,
        AuthenticatorManagerListener,
        alias_qualifier=listener_qualifier,
        target_qualifier=listener_qualifier,
    )

    async def access_listener(
        storage: TokenStorageInterface,
        decision_manager: AccessDecisionManagerInterface,
    ) -> AccessListener:
        """Build the chain step that decides the firewall's access rules."""
        return AccessListener(storage, decision_manager, access_map)

    access_listener.__annotations__ = {
        "storage": TokenStorageInterface,
        "decision_manager": AccessDecisionManagerInterface,
        "return": AccessListener,
    }
    access_listener.__name__ = f"access_listener_{name}"
    access_listener.__qualname__ = access_listener.__name__
    _ = services.set(access_listener, qualifier=access_listener_qualifier, lifetime="scoped")
    services.alias(
        FirewallListenerInterface,
        AccessListener,
        alias_qualifier=access_listener_qualifier,
        target_qualifier=access_listener_qualifier,
    )

    async def firewall_context(  # noqa: PLR0913, PLR0917 -- a wiring factory gathering one firewall's parts
        manager: Annotated[AuthenticatorManager, Target(manager_qualifier)],
        access_listener: Annotated[AccessListener, Target(access_listener_qualifier)],
        authenticators: ServiceLocator[AuthenticatorInterface],
        responses: ResponseFactoryInterface,
        storage: TokenStorageInterface,
        trust_resolver: AuthenticationTrustResolverInterface,
        bridge: StarletteHttpFactoryInterface,
        chain: ServiceLocator[FirewallListenerInterface],
        listeners: Sequence[str] = (),
        denied: object | None = None,
        scope_denied: object | None = None,
        scope_constraint: object | None = None,
        logout: object | None = None,
        logger: LoggerInterface | None = None,
    ) -> FirewallContext:
        available = {
            qualifier: await authenticators.get(qualifier) for qualifier in auth_qualifiers
        }
        entry_point = (
            cast(
                "AuthenticationEntryPointInterface",
                cast("object", available[entry_point_qualifier]),
            )
            if entry_point_qualifier is not None
            else None
        )
        scope_denied_handler = InsufficientScopeAccessDeniedHandler(
            responses,
            realm,
            inner=cast("AccessDeniedHandlerInterface | None", scope_denied),
            resource_metadata_uri=scope_resource_metadata_uri,
            sender_constraint=cast("SenderConstraintInterface | None", scope_constraint),
        )
        exception_listener = ExceptionListener(
            storage,
            trust_resolver,
            responses,
            bridge,
            name,
            entry_point=entry_point,
            access_denied_handler=cast("AccessDeniedHandlerInterface | None", denied),
            scope_denied_handler=scope_denied_handler,
            stateless=firewall.stateless,
            logger=logger,
        )
        return FirewallContext(
            name=name,
            authenticator_manager=manager,
            access_listener=access_listener,
            entry_point=entry_point,
            access_denied_handler=cast("AccessDeniedHandlerInterface | None", denied),
            scope_denied_handler=scope_denied_handler,
            listeners=tuple([await chain.get(qualifier) for qualifier in listeners]),
            exception_listener=exception_listener,
            logout_listener=cast("FirewallListenerInterface | None", logout),
        )

    annotations: dict[str, object] = {
        "manager": Annotated[AuthenticatorManager, Target(manager_qualifier)],
        "access_listener": Annotated[AccessListener, Target(access_listener_qualifier)],
        "authenticators": ServiceLocator[AuthenticatorInterface],
        "responses": ResponseFactoryInterface,
        "storage": TokenStorageInterface,
        "trust_resolver": AuthenticationTrustResolverInterface,
        "bridge": StarletteHttpFactoryInterface,
        "chain": ServiceLocator[FirewallListenerInterface],
        "return": FirewallContext,
    }
    if access_denied is not None:
        annotations["denied"] = access_denied
    if scope_denied is not None:
        annotations["scope_denied"] = scope_denied
    if scope_constraint_qualifier is not None:
        annotations["scope_constraint"] = Annotated[
            SenderConstraintInterface, Target(scope_constraint_qualifier)
        ]
    if logout_listener is not None:
        annotations["logout"] = Annotated[LogoutListener, Target(logout_listener)]
    if logging_active:
        annotations["logger"] = LoggerInterface
    firewall_context.__annotations__ = annotations
    firewall_context.__name__ = f"firewall_context_{name}"
    firewall_context.__qualname__ = firewall_context.__name__
    chain = (listener_qualifier, access_listener_qualifier, *extra_listeners, *firewall.listeners)
    if context_listener is not None:
        chain = (context_listener, *chain)
    if channel_listener is not None:
        chain = (channel_listener, *chain)
    _ = services.set(firewall_context, qualifier=name, lifetime="scoped").set_argument(
        "listeners",
        chain,
    )

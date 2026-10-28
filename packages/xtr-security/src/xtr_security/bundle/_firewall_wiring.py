"""The per-firewall wiring: every context, gathered into the firewall map."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

from xtr_dependency_injection import ServiceLocator
from xtr_security_http import (
    AccessListener,
    AccessMap,
    FirewallListenerInterface,
    FirewallMapInterface,
)
from xtr_security_http.firewall_map import FirewallMap as HttpFirewallMap

from xtr_security.bundle._authenticator_wiring import register_authenticators
from xtr_security.bundle._channel_wiring import register_channel_listener
from xtr_security.bundle._context_wiring import register_context_factory
from xtr_security.bundle._csrf_wiring import firewall_asks_for_csrf, register_csrf_token_manager
from xtr_security.bundle._dispatcher_wiring import register_dispatcher, register_shared_listeners
from xtr_security.bundle._firewall_refusals import (
    refuse_a_back_channel_logout_on_a_stateless_firewall,
    refuse_a_form_login_on_a_stateless_firewall,
    refuse_csrf_route_markers_on_a_stateless_firewall,
)
from xtr_security.bundle._logout_wiring import (
    logout_context_key,
    register_logout,
    register_logout_url_generator,
)
from xtr_security.bundle._remember_me_wiring import (
    register_remember_me_listeners,
    register_remember_me_response_listener,
    remember_me_settings_of,
)
from xtr_security.bundle._stateful_wiring import (
    register_context_listener,
    register_session_save_listener,
    register_session_strategy,
)
from xtr_security.bundle._switch_user_wiring import (
    register_impersonate_url_generator,
    register_switch_user,
)
from xtr_security.bundle._throttling_wiring import register_login_throttling
from xtr_security.bundle.firewall_context import FirewallContext
from xtr_security.bundle.oidc_configs import OidcLoginConfig
from xtr_security.factory.oidc_login_factory import oidc_token_refresh_listener_name

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping, Sequence

    from xtr_dependency_injection import ServiceConfigurator
    from xtr_http_foundation.request_matcher_interface import RequestMatcherInterface
    from xtr_security_core import AccessDecisionManagerInterface, TokenStorageInterface
    from xtr_security_http.authentication.authenticator_manager_interface import (
        AuthenticatorManagerInterface,
    )

    from xtr_security.bundle.security_config import SecurityConfig
    from xtr_security.firewall_config import FirewallConfig
    from xtr_security.switch_user_config import SwitchUserConfig

__all__ = ["build_firewall_map"]


def build_firewall_map(
    services: ServiceConfigurator,
    config: SecurityConfig,
    *,
    clock_active: bool,
    logging_active: bool = False,
) -> None:
    """Register a firewall context per firewall and the HTTP edge's firewall map.

    For each firewall this registers its authenticators through their factories,
    its own dispatcher with the listeners only it runs, and a context factory
    that gathers an authenticator manager, an access map, an entry point and the
    firewall's OpenAPI scheme. The listeners every secured firewall shares join
    the main dispatcher, once. A final factory asks a locator for every context,
    by firewall name, and pairs each with its matcher into the map.
    """
    # The forgery-token manager is one service of the request, registered
    # when any secured firewall's configuration asks for a token: the
    # checker's remove-if-missing marker watches the interface, so the
    # manager's arrival is what keeps the route marker's checker alive.
    csrf_wired = any(
        firewall.security and firewall_asks_for_csrf(firewall)
        for firewall in config.firewalls.values()
    )
    if csrf_wired:
        register_csrf_token_manager(services)
    # The response side of a stateful firewall: the token write-back and the
    # session save. Registered while any stateful firewall is configured;
    # the save listener carries the same remove-if-missing marker over the
    # application's session storage as the context step it serves.
    if any(firewall.security and not firewall.stateless for firewall in config.firewalls.values()):
        register_session_save_listener(services)
    # The response half of a remember-me cookie: one listener for the
    # application, on the main dispatcher, registered while any firewall's
    # logins are remembered.
    if any(
        firewall.security and remember_me_settings_of(firewall.authenticators) is not None
        for firewall in config.firewalls.values()
    ):
        register_remember_me_response_listener(services)

    matchers: dict[str, RequestMatcherInterface] = {}
    logout_registrations: dict[str, tuple[str, str | None]] = {}
    switch_user_registrations: dict[str, SwitchUserConfig] = {}
    for name, firewall in config.firewalls.items():
        matchers[name] = firewall.to_matcher()
        _build_firewall_context(
            services,
            config,
            name,
            firewall,
            logout_registrations,
            csrf_wired=csrf_wired,
            logging_active=logging_active,
        )
        if firewall.security and firewall.switch_user is not None:
            switch_user_registrations[name] = firewall.switch_user
    if any(firewall.security for firewall in config.firewalls.values()):
        register_shared_listeners(services, clock_active=clock_active)
    if logout_registrations:
        register_logout_url_generator(services, logout_registrations)
    if switch_user_registrations:
        register_impersonate_url_generator(
            services, switch_user_registrations, csrf_wired=csrf_wired
        )

    _ = services.set(firewall_map_factory(matchers), lifetime="scoped")
    services.alias(FirewallMapInterface, HttpFirewallMap)


def _build_firewall_context(  # noqa: PLR0913 -- a wiring call gathering one firewall's parts
    services: ServiceConfigurator,
    config: SecurityConfig,
    name: str,
    firewall: FirewallConfig,
    logout_registrations: dict[str, tuple[str, str | None]],
    *,
    csrf_wired: bool,
    logging_active: bool = False,
) -> None:
    """Register everything one firewall needs: its dispatcher, authenticators and context."""
    if not firewall.security:
        _register_open_context(services, name, firewall)
    else:
        refuse_a_back_channel_logout_on_a_stateless_firewall(name, firewall)
        refuse_a_form_login_on_a_stateless_firewall(name, firewall)
        refuse_csrf_route_markers_on_a_stateless_firewall(name, firewall)
        provider_qualifier = firewall.provider
        register_dispatcher(services, name, firewall, provider_qualifier)
        auth_qualifiers, entry_point_qualifier = register_authenticators(
            services, config, name, firewall, provider_qualifier
        )
        access_map = AccessMap()
        channel_rules = False
        for rule in config.access_control:
            if rule.firewall in (None, name):
                access_map.add(rule.to_matcher(), rule.attribute, rule.channel)
                channel_rules = channel_rules or rule.channel is not None
        channel_listener = None
        if channel_rules:
            channel_listener = register_channel_listener(
                services,
                name,
                access_map,
                http_port=config.http_port,
                https_port=config.https_port,
            )
        context_listener = None
        logout_listener = None
        if not firewall.stateless:
            context_listener = register_context_listener(
                services, name, firewall, provider_qualifier
            )
            register_session_strategy(services, name, firewall, csrf_wired=csrf_wired)
        if firewall.logout is not None:
            logout_listener = register_logout(services, name, firewall, firewall.logout)
            logout_registrations[name] = (
                firewall.logout.path,
                logout_context_key(name, firewall),
            )
        remember_me = remember_me_settings_of(firewall.authenticators)
        if remember_me is not None:
            register_remember_me_listeners(services, name, remember_me)
        if firewall.login_throttling is not None:
            register_login_throttling(services, name, firewall.login_throttling)
        extra_listeners = (
            (oidc_token_refresh_listener_name(name),)
            if any(
                isinstance(authenticator, OidcLoginConfig)
                for authenticator in firewall.authenticators
            )
            else ()
        )
        if firewall.switch_user is not None:
            extra_listeners = (
                *extra_listeners,
                register_switch_user(
                    services,
                    name,
                    firewall,
                    firewall.switch_user,
                    provider_qualifier,
                    csrf_wired=csrf_wired,
                ),
            )
        register_context_factory(
            services,
            name,
            firewall,
            auth_qualifiers=auth_qualifiers,
            entry_point_qualifier=entry_point_qualifier,
            access_map=access_map,
            expose=config.expose_security_errors,
            extra_listeners=extra_listeners,
            context_listener=context_listener,
            logout_listener=logout_listener,
            channel_listener=channel_listener,
            logging_active=logging_active,
        )


def _register_open_context(
    services: ServiceConfigurator,
    name: str,
    firewall: FirewallConfig,
) -> None:
    """Register the context of an open (``security=False``) firewall.

    The firewall parks its listener chain on the context definition's
    ``listeners`` argument — the P2.1 convention the sorting pass reads — so
    the chain is ordered before the context resolves it through the locator.
    An open firewall carries no exception listener: it authenticates nothing,
    so the global exception listener answers its errors the way it answers
    every request's.
    """

    async def firewall_context(
        chain: ServiceLocator[FirewallListenerInterface],
        listeners: Sequence[str] = (),
    ) -> FirewallContext:
        null = _NullManager()
        return FirewallContext(
            name=name,
            authenticator_manager=cast("AuthenticatorManagerInterface", cast("object", null)),
            access_listener=AccessListener(
                cast("TokenStorageInterface", cast("object", null)),
                cast("AccessDecisionManagerInterface", cast("object", null)),
                AccessMap(),
            ),
            security=False,
            listeners=tuple([await chain.get(qualifier) for qualifier in listeners]),
        )

    firewall_context.__annotations__ = {
        "chain": ServiceLocator[FirewallListenerInterface],
        "return": FirewallContext,
    }
    firewall_context.__name__ = f"firewall_context_{name}"
    firewall_context.__qualname__ = firewall_context.__name__
    # Scoped like the secured context beside it: the chain locator it reads
    # covers every firewall listener, and a secured firewall's manager
    # listener is scoped with the manager it runs.
    _ = services.set(firewall_context, qualifier=name, lifetime="scoped").set_argument(
        "listeners", firewall.listeners
    )


def firewall_map_factory(
    matchers: Mapping[str, RequestMatcherInterface],
) -> Callable[..., Awaitable[HttpFirewallMap]]:
    """Return the factory pairing every firewall context with its matcher, in order.

    With no firewalls the locator is empty, asked for nothing, and the map is
    empty too.
    """
    ordered = dict(matchers)

    async def firewall_map(contexts: ServiceLocator[FirewallContext]) -> HttpFirewallMap:
        return HttpFirewallMap(
            [(matcher, await contexts.get(name)) for name, matcher in ordered.items()]
        )

    return firewall_map


@final
class _NullManager:
    """The authenticator manager of an open firewall: it never runs."""

    __slots__ = ()

    def supports(self, request: object, state: object) -> bool | None:
        """Support nothing: an open firewall authenticates no request."""
        del request, state
        return False

    async def authenticate_request(self, request: object, state: object) -> None:
        """Do nothing: an open firewall lets every request through."""
        del request, state

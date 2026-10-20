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
from xtr_security.bundle._context_wiring import register_context_factory
from xtr_security.bundle._csrf_wiring import firewall_asks_for_csrf, register_csrf_token_manager
from xtr_security.bundle._dispatcher_wiring import register_dispatcher, register_shared_listeners
from xtr_security.bundle._logout_wiring import (
    register_logout,
    register_logout_url_generator,
)
from xtr_security.bundle._stateful_wiring import (
    register_context_listener,
    register_session_strategy,
)
from xtr_security.bundle.authenticator_configs import FormLoginConfig
from xtr_security.bundle.firewall_context import FirewallContext
from xtr_security.bundle.oidc_configs import OidcLoginConfig
from xtr_security.exception import InvalidConfigurationError
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

__all__ = ["build_firewall_map"]


def build_firewall_map(
    services: ServiceConfigurator,
    config: SecurityConfig,
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

    matchers: dict[str, RequestMatcherInterface] = {}
    logout_registrations: dict[str, tuple[str, str | None]] = {}
    for name, firewall in config.firewalls.items():
        matchers[name] = firewall.to_matcher()
        _build_firewall_context(
            services, config, name, firewall, logout_registrations, csrf_wired=csrf_wired
        )
    if any(firewall.security for firewall in config.firewalls.values()):
        register_shared_listeners(services)
    if logout_registrations:
        register_logout_url_generator(services, logout_registrations)

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
) -> None:
    """Register everything one firewall needs: its dispatcher, authenticators and context."""
    if not firewall.security:
        _register_open_context(services, name, firewall)
    else:
        _refuse_back_channel_logout_on_a_stateless_firewall(name, firewall)
        _refuse_a_form_login_on_a_stateless_firewall(name, firewall)
        provider_qualifier = firewall.provider
        register_dispatcher(services, name, firewall, provider_qualifier)
        auth_qualifiers, entry_point_qualifier = register_authenticators(
            services, config, name, firewall, provider_qualifier
        )
        access_map = AccessMap()
        for rule in config.access_control:
            if rule.firewall in (None, name):
                access_map.add(rule.to_matcher(), rule.attribute)
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
                firewall.context_key if firewall.context_key is not None else name,
            )
        register_context_factory(
            services,
            name,
            firewall,
            auth_qualifiers=auth_qualifiers,
            entry_point_qualifier=entry_point_qualifier,
            access_map=access_map,
            expose=config.expose_security_errors,
            extra_listeners=(
                (oidc_token_refresh_listener_name(name),)
                if any(
                    isinstance(authenticator, OidcLoginConfig)
                    for authenticator in firewall.authenticators
                )
                else ()
            ),
            context_listener=context_listener,
            logout_listener=logout_listener,
        )


def _refuse_back_channel_logout_on_a_stateless_firewall(
    name: str,
    firewall: FirewallConfig,
) -> None:
    """Refuse a back-channel logout a stateless firewall could never act on.

    The ended sessions a back-channel logout records are acted on by the
    refreshed-user check, which only a stateful firewall's context listener
    announces: on a stateless firewall the recording would be machinery
    nothing reads, reading as protection while refusing nothing.
    """
    for authenticator in firewall.authenticators:
        if (
            isinstance(authenticator, OidcLoginConfig)
            and authenticator.backchannel_logout is not None
            and authenticator.backchannel_logout.enable
            and firewall.stateless
        ):
            raise InvalidConfigurationError(
                f'The OIDC login of the firewall "{name}" asks for a back-channel '
                "logout, which needs a stateful firewall; set stateless=False.",
            )


def _refuse_a_form_login_on_a_stateless_firewall(
    name: str,
    firewall: FirewallConfig,
) -> None:
    """Refuse a form login on a firewall that keeps no session.

    The login's errors are stored on the session and its success rotates it;
    on a stateless firewall both would silently go nowhere, reading as a
    login while logging nothing in.

    Raises:
        InvalidConfigurationError: When a stateless firewall configures a
            form login.
    """
    if firewall.stateless and any(
        isinstance(authenticator, FormLoginConfig) for authenticator in firewall.authenticators
    ):
        raise InvalidConfigurationError(
            f'The form login of the firewall "{name}" needs the session its errors '
            "are stored in and its success rotates; set stateless=False.",
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

"""Turning a :class:`SecurityConfig` into the container definitions it describes.

Split out of the bundle so each concern reads on its own: the voters and their
optional tracing, the password hashers, the user providers, and — the large one —
the per-firewall wiring that gathers an authenticator manager, an access map, an
entry point and a scoped dispatcher into a :class:`FirewallContext`, and every
context into a :class:`FirewallMap`.

Every factory declares the services it needs as typed parameters — a bare type
for an unqualified service, ``Annotated[T, Target(name)]`` for a qualified one,
``Mapping[Hashable, T]`` for a set collected by type, and
``ServiceLocator[T]`` for the same set reached lazily by name — so none is handed
the whole container to probe. A factory built per firewall or per configured name
is a closure that captures the static parts of its firewall (its name, its access
map, the qualifiers of its authenticators) and has the container fill the rest.
"""

from __future__ import annotations

from collections.abc import Hashable, Mapping
from typing import TYPE_CHECKING, Annotated, cast, final

# These types annotate factory parameters and returns the container reads at
# runtime, so they must be importable when it does — never under TYPE_CHECKING.
from xtr_dependency_injection import ServiceKey, ServiceLocator, Target, named_factory
from xtr_event_dispatcher import EventDispatcherInterface as ConcreteEventDispatcher
from xtr_event_dispatcher import ScopedEventDispatcher
from xtr_event_dispatcher_contracts import EventDispatcherInterface
from xtr_password_hasher import (
    PasswordHasherFactory,
    PasswordHasherFactoryInterface,
    PasswordHasherInterface,
    UserPasswordHasher,
    UserPasswordHasherInterface,
    create_auto_password_hasher,
)
from xtr_security_core import (
    AccessDecisionManagerInterface,
    AuthenticatedVoter,
    AuthenticationTrustResolverInterface,
    ClosureVoter,
    RoleHierarchyInterface,
    RoleHierarchyVoter,
    TokenStorageInterface,
)
from xtr_security_core.user.user_provider_interface import UserProviderInterface
from xtr_security_http import (
    AccessListener,
    AccessMap,
    AuthenticatorManager,
    FirewallMapInterface,
    InsufficientScopeAccessDeniedHandler,
    OAuth2ScopeVoter,
)
from xtr_security_http.access_token.access_token_extractor_interface import (
    AccessTokenExtractorInterface,
)
from xtr_security_http.authenticator.authenticator_interface import (
    AuthenticatorInterface,
)
from xtr_security_http.event_listener import (
    CheckCredentialsListener,
    PasswordMigratingListener,
    UserCheckerListener,
    UserProviderListener,
)

from xtr_security.bundle._password_hasher_build import build_hasher
from xtr_security.bundle.authenticator_configs import AccessTokenConfig
from xtr_security.bundle.password_hasher_configs import ServiceHasherConfig
from xtr_security.bundle.security_config import SecurityConfig
from xtr_security.exception import InvalidConfigurationError
from xtr_security.firewall_context import FirewallContext
from xtr_security.firewall_map import FirewallMap

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from fastapi.security.base import SecurityBase
    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator
    from xtr_security_core.user.user_checker_interface import UserCheckerInterface
    from xtr_security_http.authentication.authenticator_manager_interface import (
        AuthenticatorManagerInterface,
    )
    from xtr_security_http.authenticator.passport.badge.badge_interface import BadgeInterface
    from xtr_security_http.authorization.access_denied_handler_interface import (
        AccessDeniedHandlerInterface,
    )
    from xtr_security_http.entry_point.authentication_entry_point_interface import (
        AuthenticationEntryPointInterface,
    )
    from xtr_security_http.request_matcher.request_matcher_interface import RequestMatcherInterface

    from xtr_security.access_token import TokenHandlerFactoryInterface
    from xtr_security.bundle.password_hasher_configs import HasherConfig
    from xtr_security.factory import AuthenticatorFactoryInterface
    from xtr_security.factory.access_token_factory import AccessTokenFactory
    from xtr_security.firewall_config import FirewallConfig
    from xtr_security.user_provider import UserProviderFactoryInterface

__all__ = [
    "DUMMY_PASSWORD_HASHER_QUALIFIER",
    "VOTER_TAG",
    "build_firewall_map",
    "register_hashers",
    "register_user_providers",
    "register_voters",
]

VOTER_TAG = "security.voter"
"""The tag every voter carries, so the decision manager collects them all."""

DUMMY_PASSWORD_HASHER_QUALIFIER = "security.dummy_password_hasher"  # noqa: S105 -- a service qualifier, not a secret
"""The qualifier the timing-guard dummy hasher is registered under.

The per-firewall credentials check burns a verify against this hasher for an
unknown user, so a bad username costs the same as a bad password. It is a
service of its own — not the user hasher — so a test can override it with a
counting hasher and prove the burn ran through the wired dispatcher.
"""


@final
class _ServiceHasher:
    """The type a hasher the application registered is collected under.

    A password hasher configured as a service is forwarded under this private
    type so the hasher factory can gather every one into a ``Mapping`` keyed by
    a qualifier of its own, without pulling the whole container in.
    """

    __slots__ = ()


def _qualified(service: type, qualifier: Hashable) -> object:
    """Return the injection annotation selecting ``service`` under ``qualifier``.

    Built at runtime from a configured type, so the second type checker reads the
    subscript as a static type expression it is not — hence the suppression; the
    container evaluates it as the marker it forms.
    """
    return Annotated[service, Target(qualifier)]  # ty: ignore[invalid-type-form] -- runtime marker


def register_voters(services: ServiceConfigurator) -> None:
    """Register the built-in voters, each tagged so the manager collects it.

    The role voter expands through the role hierarchy; the authenticated voter
    reads the trust resolver; the OAuth2 scope voter and the closure voter round
    out the set. Each is registered as a factory and tagged with
    :data:`VOTER_TAG`; the bundle wraps every collected voter in a
    :class:`~xtr_security_core.TraceableVoter` when tracing is on.
    """
    _ = services.set(_role_hierarchy_voter, qualifier="role_hierarchy").add_tag(VOTER_TAG)
    _ = services.set(_authenticated_voter, qualifier="authenticated").add_tag(VOTER_TAG)
    _ = services.set(_oauth2_scope_voter, qualifier="oauth2_scope").add_tag(VOTER_TAG)
    _ = services.set(_closure_voter, qualifier="closure").add_tag(VOTER_TAG)


def _role_hierarchy_voter(role_hierarchy: RoleHierarchyInterface) -> RoleHierarchyVoter:
    """Build the role voter that expands through the role hierarchy."""
    return RoleHierarchyVoter(role_hierarchy)


def _authenticated_voter(
    trust_resolver: AuthenticationTrustResolverInterface,
) -> AuthenticatedVoter:
    """Build the voter that grants by authentication strength."""
    return AuthenticatedVoter(trust_resolver)


def _oauth2_scope_voter() -> OAuth2ScopeVoter:
    """Build the voter that grants by the scopes a token carries."""
    return OAuth2ScopeVoter()


def _closure_voter() -> ClosureVoter:
    """Build the voter that runs a callable attribute."""
    return ClosureVoter()


def register_hashers(services: ServiceConfigurator, config: SecurityConfig) -> None:
    """Register the password hasher factory and the user hasher from the config.

    Every hasher configured as a service is forwarded under :class:`_ServiceHasher`
    so the factory gathers them by injecting a ``Mapping``; the other hasher
    configurations the factory closes over and builds itself. The factory and the
    user hasher are registered under their interfaces so a service asks for either
    by type.
    """
    static_hashers: dict[type | str, HasherConfig] = {}
    service_entries: list[tuple[type | str, str]] = []
    for index, (key, hasher_config) in enumerate(config.password_hashers.items()):
        if isinstance(hasher_config, ServiceHasherConfig):
            qualifier = f"security_service_hasher_{index}"
            forward = _service_hasher_forward(hasher_config.service, hasher_config.qualifier)
            _ = services.set(named_factory(forward, qualifier), qualifier=qualifier)
            service_entries.append((key, qualifier))
        else:
            static_hashers[key] = hasher_config

    _ = services.set(_password_hasher_factory(static_hashers, tuple(service_entries)))
    services.alias(PasswordHasherFactoryInterface, PasswordHasherFactory)
    _ = services.set(_user_password_hasher)
    services.alias(UserPasswordHasherInterface, UserPasswordHasher)
    _ = services.set(_dummy_password_hasher, qualifier=DUMMY_PASSWORD_HASHER_QUALIFIER)


def _dummy_password_hasher() -> PasswordHasherInterface:
    """Build the timing-guard hasher an unknown user's credentials check burns."""
    return create_auto_password_hasher()


def _service_hasher_forward(
    service: type,
    qualifier: Hashable | None,
) -> Callable[..., Awaitable[_ServiceHasher]]:
    """Return a factory forwarding an application hasher service under :class:`_ServiceHasher`."""

    async def service_hasher(hasher: object) -> _ServiceHasher:
        return cast("_ServiceHasher", hasher)

    service_hasher.__annotations__ = {
        "hasher": _qualified(service, qualifier) if qualifier is not None else service,
        "return": _ServiceHasher,
    }
    return service_hasher


def _password_hasher_factory(
    static_hashers: Mapping[type | str, HasherConfig],
    service_entries: Sequence[tuple[type | str, str]],
) -> Callable[..., Awaitable[PasswordHasherFactory]]:
    """Return the factory building the :class:`PasswordHasherFactory` from the config.

    The static configurations are built into ready hashers here — the factory
    itself takes instances, not configuration — and the service hashers a
    container provides are gathered in beside them.
    """
    fixed = {key: build_hasher(config) for key, config in static_hashers.items()}

    async def password_hasher_factory(
        service_hashers: Mapping[Hashable, _ServiceHasher] | None = None,
    ) -> PasswordHasherFactory:
        resolved: dict[type | str, PasswordHasherInterface] = dict(fixed)
        if service_hashers is not None:
            for config_key, qualifier in service_entries:
                resolved[config_key] = cast(
                    "PasswordHasherInterface", cast("object", service_hashers[qualifier])
                )
        return PasswordHasherFactory(resolved)

    if service_entries:
        password_hasher_factory.__annotations__ = {
            "service_hashers": Mapping[Hashable, _ServiceHasher],
            "return": PasswordHasherFactory,
        }
    return password_hasher_factory


def _user_password_hasher(factory: PasswordHasherFactoryInterface) -> UserPasswordHasher:
    """Build the user password hasher over the configured factory."""
    return UserPasswordHasher(factory)


def register_user_providers(services: ServiceConfigurator, config: SecurityConfig) -> None:
    """Register each configured user provider, aliased to the provider interface.

    A provider is registered under its factory's key and the provider name as
    qualifier, then aliased to
    :class:`~xtr_security_core.user.user_provider_interface.UserProviderInterface`
    under the same name, so a firewall and a chain resolve any provider uniformly
    by name.
    """
    factories = {factory.config_type: factory for factory in config.user_provider_factories}
    for name, provider_config in config.providers.items():
        factory = _match_factory(
            factories,
            provider_config,
            f'the user provider "{name}"',
        )
        key = factory.create(services, _NO_BUILDER, name, provider_config)
        services.alias(
            UserProviderInterface,
            key[0],
            alias_qualifier=name,
            target_qualifier=key[1],
        )


def build_firewall_map(
    services: ServiceConfigurator,
    config: SecurityConfig,
) -> None:
    """Register a :class:`FirewallContext` per firewall and a :class:`FirewallMap`.

    For each firewall this registers its authenticators through their factories,
    a scoped dispatcher carrying the http listeners, and a context factory that
    gathers an authenticator manager, an access map, an entry point and the
    firewall's OpenAPI scheme. A final factory asks a locator for every context,
    by firewall name, and pairs each with its matcher and its configuration into
    the map.
    """
    matchers: dict[str, RequestMatcherInterface] = {}
    configs: dict[str, FirewallConfig] = {}
    for name, firewall in config.firewalls.items():
        matchers[name] = firewall.to_matcher()
        configs[name] = firewall
        _build_firewall_context(services, config, name, firewall)

    _ = services.set(_firewall_map_factory(matchers, configs), lifetime="scoped")
    services.alias(FirewallMapInterface, FirewallMap)


def _build_firewall_context(
    services: ServiceConfigurator,
    config: SecurityConfig,
    name: str,
    firewall: FirewallConfig,
) -> None:
    """Register everything one firewall needs: its dispatcher, authenticators and context."""
    if not firewall.security:
        _register_open_context(services, name)
    else:
        provider_qualifier = firewall.provider
        _register_dispatcher(services, name, firewall, provider_qualifier)
        auth_qualifiers, entry_point_qualifier = _register_authenticators(
            services, config, name, firewall, provider_qualifier
        )
        access_map = AccessMap()
        for rule in config.access_control:
            if rule.firewall in (None, name):
                access_map.add(rule.to_matcher(), rule.attribute)
        _register_context_factory(
            services,
            name,
            firewall,
            auth_qualifiers=auth_qualifiers,
            entry_point_qualifier=entry_point_qualifier,
            access_map=access_map,
        )


def _register_open_context(services: ServiceConfigurator, name: str) -> None:
    """Register the context of an open (``security=False``) firewall."""
    from fastapi.security import HTTPBearer  # noqa: PLC0415 -- http-only

    def firewall_context() -> FirewallContext:
        null = _NullManager()
        return FirewallContext(
            name=name,
            authenticator_manager=cast("AuthenticatorManagerInterface", cast("object", null)),
            access_listener=AccessListener(
                AccessMap(),
                cast("AccessDecisionManagerInterface", cast("object", null)),
            ),
            dispatcher=cast("EventDispatcherInterface", cast("object", _NullDispatcher())),
            scheme=HTTPBearer(auto_error=False),
            security=False,
        )

    firewall_context.__name__ = f"firewall_context_{name}"
    firewall_context.__qualname__ = firewall_context.__name__
    _ = services.set(firewall_context, qualifier=name)


def _register_dispatcher(
    services: ServiceConfigurator,
    name: str,
    firewall: FirewallConfig,
    provider_qualifier: str | None,
) -> None:
    """Register the firewall's own scoped dispatcher with the http listeners on it.

    The global dispatcher, the password hasher and — when the firewall names them
    — its user provider and user checker are injected; the listeners are wired
    onto a :class:`ScopedEventDispatcher` over the global one.
    """
    user_checker = firewall.user_checker

    async def firewall_dispatcher(
        global_dispatcher: ConcreteEventDispatcher,
        hasher: UserPasswordHasherInterface,
        dummy_hasher: PasswordHasherInterface,
        provider: UserProviderInterface | None = None,
        checker: object | None = None,
    ) -> EventDispatcherInterface:
        from xtr_security_core import InMemoryUserChecker  # noqa: PLC0415 -- default checker

        scoped = ScopedEventDispatcher(global_dispatcher)
        if provider is not None:
            scoped.add_subscriber(UserProviderListener(provider))
        resolved_checker = checker if checker is not None else InMemoryUserChecker()
        scoped.add_subscriber(UserCheckerListener(cast("UserCheckerInterface", resolved_checker)))
        scoped.add_subscriber(CheckCredentialsListener(hasher, dummy_hasher))
        scoped.add_subscriber(PasswordMigratingListener(hasher))
        return scoped

    annotations: dict[str, object] = {
        "global_dispatcher": ConcreteEventDispatcher,
        "hasher": UserPasswordHasherInterface,
        "dummy_hasher": Annotated[PasswordHasherInterface, Target(DUMMY_PASSWORD_HASHER_QUALIFIER)],
        "return": EventDispatcherInterface,
    }
    if provider_qualifier is not None:
        annotations["provider"] = Annotated[UserProviderInterface, Target(provider_qualifier)]
    if user_checker is not None:
        annotations["checker"] = user_checker
    firewall_dispatcher.__annotations__ = annotations
    firewall_dispatcher.__name__ = f"firewall_dispatcher_{name}"
    firewall_dispatcher.__qualname__ = firewall_dispatcher.__name__
    _ = services.set(firewall_dispatcher, qualifier=name, lifetime="scoped")


def _register_authenticators(
    services: ServiceConfigurator,
    config: SecurityConfig,
    name: str,
    firewall: FirewallConfig,
    provider_qualifier: str | None,
) -> tuple[tuple[str, ...], str | None]:
    """Register the firewall's authenticators, aliased for collection, sorted by priority.

    Each authenticator is aliased to
    :class:`~xtr_security_http.authenticator.authenticator_interface.AuthenticatorInterface`
    under a qualifier of its own, so the context factory gathers them from a
    ``Mapping`` and picks this firewall's, in order. Returns those qualifiers and
    the one the entry point answers on.
    """
    factories = _authenticator_factories(config)
    token_handler_factories = {factory.key: factory for factory in config.token_handler_factories}
    user_provider = (
        (UserProviderInterface, provider_qualifier) if provider_qualifier is not None else None
    )
    keys: list[tuple[int, ServiceKey]] = []
    for authenticator_config in firewall.authenticators:
        factory = _match_authenticator_factory(factories, authenticator_config, name)
        prepared = _prepare_factory(factory, token_handler_factories)
        created = prepared.create_authenticator(
            services,
            _NO_BUILDER,
            name,
            authenticator_config,
            user_provider,
        )
        keys.extend((prepared.priority, key) for key in created)
    keys.sort(key=lambda entry: -entry[0])
    ordered = [key for _, key in keys]

    qualifiers: list[str] = []
    for index, key in enumerate(ordered):
        qualifier = f"{name}#authenticator#{index}"
        services.alias(
            AuthenticatorInterface,
            key[0],
            alias_qualifier=qualifier,
            target_qualifier=key[1],
        )
        qualifiers.append(qualifier)
    entry_point_qualifier = _resolve_entry_point(config, name, firewall, ordered, qualifiers)
    return tuple(qualifiers), entry_point_qualifier


def _prepare_factory(
    factory: AuthenticatorFactoryInterface,
    token_handler_factories: dict[str, TokenHandlerFactoryInterface],
) -> AuthenticatorFactoryInterface:
    """Give an access-token factory the token-handler registry it needs."""
    with_registry = getattr(factory, "with_token_handler_factories", None)
    if with_registry is not None:
        return cast("AccessTokenFactory", with_registry(token_handler_factories))
    return factory


def _register_context_factory(  # noqa: PLR0913 -- a wiring call gathering one firewall's parts
    services: ServiceConfigurator,
    name: str,
    firewall: FirewallConfig,
    *,
    auth_qualifiers: tuple[str, ...],
    entry_point_qualifier: str | None,
    access_map: AccessMap,
) -> None:
    """Register the factory that gathers one firewall's parts into a context.

    The authenticators are asked of a locator by the qualifiers this firewall's
    authenticators were aliased under, so a firewall builds its own and no other
    firewall's; the manager is built over them and the injected storage and
    dispatcher; the scheme and the entry point are read off the same
    authenticators.
    """
    realm = _realm_of(firewall)
    access_denied = firewall.access_denied_handler
    expose = SecurityConfig().expose_security_errors
    required_badges = firewall.required_badges

    async def firewall_context(
        storage: TokenStorageInterface,
        dispatcher: EventDispatcherInterface,
        decision_manager: AccessDecisionManagerInterface,
        authenticators: ServiceLocator[AuthenticatorInterface],
        denied: object | None = None,
    ) -> FirewallContext:
        available = {
            qualifier: await authenticators.get(qualifier) for qualifier in auth_qualifiers
        }
        auths = list(available.values())
        manager = AuthenticatorManager(
            auths,
            storage,
            dispatcher,
            name,
            expose_security_errors=expose,
            required_badges=cast("Sequence[type[BadgeInterface]]", required_badges),
        )
        entry_point = (
            cast(
                "AuthenticationEntryPointInterface",
                cast("object", available[entry_point_qualifier]),
            )
            if entry_point_qualifier is not None
            else None
        )
        return FirewallContext(
            name=name,
            authenticator_manager=manager,
            access_listener=AccessListener(access_map, decision_manager),
            dispatcher=dispatcher,
            scheme=_scheme_from(auths),
            entry_point=entry_point,
            access_denied_handler=cast("AccessDeniedHandlerInterface | None", denied),
            scope_denied_handler=InsufficientScopeAccessDeniedHandler(realm),
        )

    annotations: dict[str, object] = {
        "storage": TokenStorageInterface,
        "dispatcher": Annotated[EventDispatcherInterface, Target(name)],
        "decision_manager": AccessDecisionManagerInterface,
        "authenticators": ServiceLocator[AuthenticatorInterface],
        "return": FirewallContext,
    }
    if access_denied is not None:
        annotations["denied"] = access_denied
    firewall_context.__annotations__ = annotations
    firewall_context.__name__ = f"firewall_context_{name}"
    firewall_context.__qualname__ = firewall_context.__name__
    _ = services.set(firewall_context, qualifier=name, lifetime="scoped")


def _firewall_map_factory(
    matchers: Mapping[str, RequestMatcherInterface],
    configs: Mapping[str, FirewallConfig],
) -> Callable[..., Awaitable[FirewallMap]]:
    """Return the factory pairing every firewall context with its matcher and config, in order.

    With no firewalls the locator is empty, asked for nothing, and the map is
    empty too.
    """
    ordered = dict(matchers)
    ordered_configs = dict(configs)

    async def firewall_map(contexts: ServiceLocator[FirewallContext]) -> FirewallMap:
        return FirewallMap(
            [
                (matcher, await contexts.get(name), ordered_configs[name])
                for name, matcher in ordered.items()
            ]
        )

    return firewall_map


def _scheme_from(authenticators: Sequence[AuthenticatorInterface]) -> SecurityBase:
    """Return the OpenAPI scheme the firewall shows: its entry-point extractor's."""
    from fastapi.security import HTTPBearer  # noqa: PLC0415 -- http-only

    for authenticator in authenticators:
        extractor = getattr(authenticator, "_extractor", None)
        if isinstance(extractor, AccessTokenExtractorInterface):
            return extractor.scheme()
    return HTTPBearer(auto_error=False, bearerFormat="JWT")


def _resolve_entry_point(
    config: SecurityConfig,
    name: str,
    firewall: FirewallConfig,
    ordered_keys: Sequence[ServiceKey],
    qualifiers: Sequence[str],
) -> str | None:
    """Resolve the qualifier of the authenticator that answers an unauthenticated request.

    The configured name when given, else the only authenticator that is itself an
    entry point; a firewall with an access rule that needs authentication and no
    resolvable entry point fails the build.
    """
    if not ordered_keys:
        return None
    if firewall.entry_point is not None:
        matched = [
            index for index, key in enumerate(ordered_keys) if key[1] == firewall.entry_point
        ]
        if not matched:
            raise InvalidConfigurationError(
                f'The firewall "{name}" names the entry point "{firewall.entry_point}", '
                f"which is not one of its authenticators.",
            )
        return qualifiers[matched[0]]
    needs_auth = any(
        rule.firewall in (None, name) and rule.attribute != "PUBLIC_ACCESS"
        for rule in config.access_control
    )
    if len(ordered_keys) == 1:
        return qualifiers[0]
    if needs_auth:
        raise InvalidConfigurationError(
            f'The firewall "{name}" has several authenticators and an access rule that '
            f"needs authentication, but no entry point to answer it; set entry_point.",
        )
    return qualifiers[0]


def _authenticator_factories(
    config: SecurityConfig,
) -> dict[type, AuthenticatorFactoryInterface]:
    """Index the authenticator factories by their configuration type."""
    return {factory.config_type: factory for factory in config.authenticator_factories}


def _match_authenticator_factory(
    factories: dict[type, AuthenticatorFactoryInterface],
    authenticator_config: object,
    firewall_name: str,
) -> AuthenticatorFactoryInterface:
    """Return the factory whose configuration type matches, or fail the build."""
    for config_type, factory in factories.items():
        if isinstance(authenticator_config, config_type):
            return factory
    raise InvalidConfigurationError(
        f"No authenticator factory handles {type(authenticator_config).__name__} "
        f'on the firewall "{firewall_name}".',
    )


def _match_factory(
    factories: dict[type, UserProviderFactoryInterface],
    provider_config: object,
    described: str,
) -> UserProviderFactoryInterface:
    """Return the user-provider factory whose configuration type matches."""
    for config_type, factory in factories.items():
        if isinstance(provider_config, config_type):
            return factory
    raise InvalidConfigurationError(
        f"No user-provider factory handles {type(provider_config).__name__} for {described}.",
    )


def _realm_of(firewall: FirewallConfig) -> str | None:
    """Read the realm off the firewall's first access-token authenticator, if any."""
    for authenticator in firewall.authenticators:
        if isinstance(authenticator, AccessTokenConfig):
            return authenticator.realm
    return None


@final
class _NullManager:
    """The authenticator manager of an open firewall: it never runs."""

    __slots__ = ()

    def supports(self, request: object) -> bool | None:
        """Support nothing: an open firewall authenticates no request."""
        del request
        return False

    async def authenticate_request(self, request: object) -> None:
        """Do nothing: an open firewall lets every request through."""
        del request


@final
class _NullDispatcher:
    """A dispatcher an open firewall never uses."""

    __slots__ = ()


# A sentinel where a factory's ``builder`` argument is not used: the built-in
# factories register services and read no other definitions.
_NO_BUILDER = cast("ContainerBuilder", cast("object", None))

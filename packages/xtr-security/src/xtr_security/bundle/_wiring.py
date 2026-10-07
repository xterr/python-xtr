"""Turning a :class:`SecurityConfig` into the container definitions it describes.

Split out of the bundle so each concern reads on its own: the voters and their
optional tracing, the password hashers, the user providers, and — the large one —
the per-firewall wiring that gathers an authenticator manager, an access map, an
entry point and the firewall's own dispatcher into a
:class:`~xtr_security.bundle.firewall_context.FirewallContext`, and every context
into the HTTP edge's :class:`~xtr_security_http.firewall_map.FirewallMap`.

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
from typing import TYPE_CHECKING, Annotated, Protocol, cast, final, runtime_checkable

# These types annotate factory parameters and returns the container reads at
# runtime, so they must be importable when it does — never under TYPE_CHECKING.
from xtr_dependency_injection import ServiceKey, ServiceLocator, Target, named_factory
from xtr_event_dispatcher.bundle import DISPATCHER_TAG, SUBSCRIBER_TAG, event_dispatcher_factory
from xtr_event_dispatcher_contracts import EventDispatcherInterface
from xtr_password_hasher import (
    PasswordHasherFactory,
    PasswordHasherFactoryInterface,
    PasswordHasherInterface,
    UserPasswordHasher,
    UserPasswordHasherInterface,
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
    ExposeSecurityLevel,
    FirewallMapInterface,
    InsufficientScopeAccessDeniedHandler,
    OAuth2ScopeVoter,
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
from xtr_security_http.firewall_map import FirewallMap as HttpFirewallMap

from xtr_security.bundle._password_hasher_build import build_hasher
from xtr_security.bundle.authenticator_configs import AccessTokenConfig
from xtr_security.bundle.firewall_context import FirewallContext
from xtr_security.bundle.firewall_dispatcher_name import firewall_dispatcher_name
from xtr_security.bundle.password_hasher_configs import AutoHasherConfig, ServiceHasherConfig
from xtr_security.exception import InvalidConfigurationError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from fastapi.security.base import SecurityBase
    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator
    from xtr_security_core.user.user_checker_interface import UserCheckerInterface
    from xtr_security_http.access_token.access_token_extractor_interface import (
        AccessTokenExtractorInterface,
    )
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
    from xtr_security.bundle.security_config import SecurityConfig
    from xtr_security.factory import AuthenticatorFactoryInterface
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
    _ = services.set(
        _dummy_password_hasher(_default_hasher_config(config)),
        qualifier=DUMMY_PASSWORD_HASHER_QUALIFIER,
    )


def _default_hasher_config(config: SecurityConfig) -> HasherConfig:
    """Return the hasher config the dummy timing-guard hasher mirrors.

    The dummy burn must cost what a real verify costs, so it is built from the
    application's first configured hasher — the default the hash command hashes
    for too. A service hasher cannot be built without the container, and nothing
    configured falls back to the secure default, so either yields
    :class:`AutoHasherConfig`.

    The guard is only worth what the mirrored hasher costs: an application whose
    default is a plaintext hasher burns nothing, so a missing user still answers
    faster than a wrong password. That is the plaintext hasher's documented
    trade, not a defect here — an application that wants the guard configures a
    real hasher as its default.
    """
    for hasher_config in config.password_hashers.values():
        if isinstance(hasher_config, ServiceHasherConfig):
            break
        return hasher_config
    return AutoHasherConfig()


def _dummy_password_hasher(
    config: HasherConfig,
) -> Callable[[], PasswordHasherInterface]:
    """Return a factory building the timing-guard hasher from ``config``."""

    def dummy_password_hasher() -> PasswordHasherInterface:
        return build_hasher(config)

    return dummy_password_hasher


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
    """Register a firewall context per firewall and the HTTP edge's firewall map.

    For each firewall this registers its authenticators through their factories,
    its own dispatcher with the listeners only it runs, and a context factory
    that gathers an authenticator manager, an access map, an entry point and the
    firewall's OpenAPI scheme. The listeners every secured firewall shares join
    the main dispatcher, once. A final factory asks a locator for every context,
    by firewall name, and pairs each with its matcher into the map.
    """
    matchers: dict[str, RequestMatcherInterface] = {}
    for name, firewall in config.firewalls.items():
        matchers[name] = firewall.to_matcher()
        _build_firewall_context(services, config, name, firewall)
    if any(firewall.security for firewall in config.firewalls.values()):
        _register_shared_listeners(services)

    _ = services.set(_firewall_map_factory(matchers), lifetime="scoped")
    services.alias(FirewallMapInterface, HttpFirewallMap)


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
            expose=config.expose_security_errors,
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
                _user_provider_listener(provider_qualifier), f"user_provider_listener_{name}"
            ),
            qualifier=dispatcher,
        ).add_tag(SUBSCRIBER_TAG, dispatcher=dispatcher)
    _ = services.set(
        named_factory(
            _user_checker_listener(firewall.user_checker), f"user_checker_listener_{name}"
        ),
        qualifier=dispatcher,
    ).add_tag(SUBSCRIBER_TAG, dispatcher=dispatcher)


def _user_provider_listener(provider_qualifier: str) -> Callable[..., UserProviderListener]:
    """Return the factory of the listener loading users from the firewall's provider."""

    def user_provider_listener(provider: UserProviderInterface) -> UserProviderListener:
        return UserProviderListener(provider)

    user_provider_listener.__annotations__ = {
        "provider": Annotated[UserProviderInterface, Target(provider_qualifier)],
        "return": UserProviderListener,
    }
    return user_provider_listener


def _user_checker_listener(user_checker: type | None) -> Callable[..., UserCheckerListener]:
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


def _register_shared_listeners(services: ServiceConfigurator) -> None:
    """Register, on the main dispatcher, the listeners every secured firewall runs.

    They reach each firewall's dispatcher through
    :class:`~xtr_security.bundle.RegisterGlobalSecurityEventListenersPass`, as an
    application's own security listeners do.
    """
    _ = services.set(_check_credentials_listener).add_tag(SUBSCRIBER_TAG)
    _ = services.set(_password_migrating_listener).add_tag(SUBSCRIBER_TAG)


def _check_credentials_listener(
    hasher: UserPasswordHasherInterface,
    dummy_hasher: Annotated[PasswordHasherInterface, Target(DUMMY_PASSWORD_HASHER_QUALIFIER)],
) -> CheckCredentialsListener:
    """Build the credentials check, with the dummy hasher an unknown user's check burns."""
    return CheckCredentialsListener(hasher, dummy_hasher)


def _password_migrating_listener(hasher: UserPasswordHasherInterface) -> PasswordMigratingListener:
    """Build the listener rehashing a password flagged as outdated."""
    return PasswordMigratingListener(hasher)


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
    if isinstance(factory, _TakesTokenHandlerFactories):
        return factory.with_token_handler_factories(token_handler_factories)
    return factory


@runtime_checkable
class _TakesTokenHandlerFactories(Protocol):
    """An authenticator factory that resolves token handlers through a registry.

    The access-token factory needs the token-handler factories to build its
    handler; another kind of authenticator factory does not. This is the shape
    the wiring tests for, instead of probing an attribute by name.
    """

    def with_token_handler_factories(
        self,
        token_handler_factories: Mapping[str, TokenHandlerFactoryInterface],
    ) -> AuthenticatorFactoryInterface:
        """Return a copy of the factory bound to ``token_handler_factories``."""
        ...


@runtime_checkable
class _HasExtractor(Protocol):
    """An authenticator exposing the extractor whose scheme a firewall shows."""

    @property
    def extractor(self) -> AccessTokenExtractorInterface:
        """The extractor that reads a token out of a request."""
        ...


def _register_context_factory(  # noqa: PLR0913 -- a wiring call gathering one firewall's parts
    services: ServiceConfigurator,
    name: str,
    firewall: FirewallConfig,
    *,
    auth_qualifiers: tuple[str, ...],
    entry_point_qualifier: str | None,
    access_map: AccessMap,
    expose: ExposeSecurityLevel,
) -> None:
    """Register the factory that gathers one firewall's parts into a context.

    The authenticators are asked of a locator by the qualifiers this firewall's
    authenticators were aliased under, so a firewall builds its own and no other
    firewall's; the manager is built over them and the injected storage and
    dispatcher; the scheme and the entry point are read off the same
    authenticators. ``expose`` is the configured
    :class:`~xtr_security_http.ExposeSecurityLevel`, threaded to the manager so a
    non-default level reaches every firewall.
    """
    realm = _realm_of(firewall)
    access_denied = firewall.access_denied_handler
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
            scheme=_scheme_from(auths),
            entry_point=entry_point,
            access_denied_handler=cast("AccessDeniedHandlerInterface | None", denied),
            scope_denied_handler=InsufficientScopeAccessDeniedHandler(realm),
        )

    annotations: dict[str, object] = {
        "storage": TokenStorageInterface,
        "dispatcher": Annotated[EventDispatcherInterface, Target(firewall_dispatcher_name(name))],
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


def _scheme_from(authenticators: Sequence[AuthenticatorInterface]) -> SecurityBase:
    """Return the OpenAPI scheme the firewall shows: its entry-point extractor's."""
    from fastapi.security import HTTPBearer  # noqa: PLC0415 -- http-only

    for authenticator in authenticators:
        if isinstance(authenticator, _HasExtractor):
            return authenticator.extractor.scheme()
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


# A sentinel where a factory's ``builder`` argument is not used: the built-in
# factories register services and read no other definitions.
_NO_BUILDER = cast("ContainerBuilder", cast("object", None))

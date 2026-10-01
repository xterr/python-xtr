"""The xtr-security bundle: the family's one integration with the container.

Reads a :class:`SecurityConfig` and puts the whole security machine under the
container — the token storage and authorization checker scoped to a request, the
voters and the decision manager, the user providers and password hashers, and,
per firewall, its own event dispatcher, authenticators, access map and entry
point, gathered into a :class:`FirewallMap`. The exception listener turns a
security error into a response on the http-kernel lifecycle, and — at boot — the
firewalls' OpenAPI schemes are filled into a per-kernel registry the generated
schema reads.
"""

from __future__ import annotations

from collections.abc import Hashable, Mapping
from typing import TYPE_CHECKING, cast, final

from typing_extensions import override
from xtr_dependency_injection import (
    Bundle,
    as_bundle,
    bundle_active,
    required_bundle,
)
from xtr_event_dispatcher.bundle import EventDispatcherBundle
from xtr_event_dispatcher_contracts import EventDispatcherInterface
from xtr_http_kernel import ExceptionEvent
from xtr_http_kernel.bundle import HttpKernelBundle
from xtr_security_core import (
    AccessDecisionManager,
    AccessDecisionManagerInterface,
    AccessDecisionStrategyInterface,
    AuthenticationTrustResolver,
    AuthenticationTrustResolverInterface,
    AuthorizationChecker,
    AuthorizationCheckerInterface,
    GuestAuthorizationCheckerInterface,
    RoleHierarchy,
    RoleHierarchyInterface,
    TokenStorage,
    TokenStorageInterface,
    TraceableVoter,
    VoterInterface,
)
from xtr_security_http import (
    ExceptionListener,
    FirewallSchemeRegistry,
)

from xtr_security.bundle.security_config import SecurityConfig
from xtr_security.firewall_map import FirewallMap
from xtr_security.security import Security

from ._firewall_scheme_middleware_factory import FirewallSchemeMiddlewareFactory
from ._wiring import (
    VOTER_TAG,
    build_firewall_map,
    register_hashers,
    register_user_providers,
    register_voters,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator

__all__ = ["SecurityBundle"]

_LISTENER_TAG = "event_dispatcher.listener"
"""The tag the event dispatcher bundle reads listeners from."""

_MIDDLEWARE_TAG = "http_kernel.middleware"
"""The tag the http-kernel bundle orders middleware factories by."""

_SCHEME_MIDDLEWARE_PRIORITY = -4096
"""The scheme-activating middleware sits innermost; it wraps only the schema read."""


@final
@required_bundle(EventDispatcherBundle)
@required_bundle(HttpKernelBundle)
@required_bundle("xtr_logging.bundle:LoggingBundle", ignore_on_invalid=True)
@required_bundle("xtr_console.bundle:ConsoleBundle", ignore_on_invalid=True)
@as_bundle("security", config=SecurityConfig)
class SecurityBundle(Bundle[SecurityConfig]):
    """Configures the xtr security family from one :class:`SecurityConfig`."""

    def __init__(self) -> None:
        """Start with a fresh per-kernel scheme registry to fill at boot."""
        self._scheme_registry = FirewallSchemeRegistry()
        self._firewall_names: tuple[str, ...] = ()
        self._strategy: AccessDecisionStrategyInterface = (
            SecurityConfig().access_decision_manager.build()
        )
        self._trace_votes = False

    @override
    def build(self, builder: ContainerBuilder) -> None:
        """Autoconfigure every application voter with the voter tag."""
        _ = builder.register_for_autoconfiguration(VoterInterface).add_tag(VOTER_TAG)

    @override
    def load_extension(
        self,
        config: SecurityConfig,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        """Register the security services from ``config``."""
        self._trace_votes = (
            config.trace_votes
            if config.trace_votes is not None
            else bool(builder.get_parameter("kernel.debug"))
        )
        self._strategy = config.access_decision_manager.build()

        _ = services.instance(RoleHierarchy(config.role_hierarchy))
        services.alias(RoleHierarchyInterface, RoleHierarchy)
        _ = services.instance(AuthenticationTrustResolver())
        services.alias(AuthenticationTrustResolverInterface, AuthenticationTrustResolver)

        register_voters(services)
        _ = services.set(
            _access_decision_manager_factory(self._strategy, trace_votes=self._trace_votes)
        ).set_argument("voter_qualifiers", ())
        services.alias(AccessDecisionManagerInterface, AccessDecisionManager)

        _ = services.set(TokenStorage, lifetime="scoped").add_tag("kernel.reset", method="reset")
        services.alias(TokenStorageInterface, TokenStorage)
        _ = services.set(_authorization_checker, lifetime="scoped")
        services.alias(AuthorizationCheckerInterface, AuthorizationChecker)
        services.alias(GuestAuthorizationCheckerInterface, AuthorizationChecker)
        _ = services.set(_security_facade, lifetime="scoped")

        register_hashers(services, config)
        register_user_providers(services, config)

        self._firewall_names = tuple(config.firewalls)
        build_firewall_map(services, config)

        _ = services.set(ExceptionListener).add_tag(
            _LISTENER_TAG,
            event=ExceptionEvent,
            method="on_exception",
        )

        _ = services.instance(self._scheme_registry)
        _ = services.set(_scheme_middleware_factory(self._scheme_registry)).add_tag(
            _MIDDLEWARE_TAG, priority=_SCHEME_MIDDLEWARE_PRIORITY
        )

        if bundle_active(builder, "console"):
            services.load("xtr_security.command")

    @override
    def process(self, builder: ContainerBuilder) -> None:
        """Collect every tagged voter and build the decision manager over them.

        Runs after every bundle loaded, so the builder holds every voter — the
        built-ins and every application voter the autoconfiguration tagged. Each
        is aliased to
        :class:`~xtr_security_core.authorization.voter.voter_interface.VoterInterface`
        under a qualifier of its own, so the manager gathers them from a
        ``Mapping`` and orders them as collected; the bundle wraps each in a
        :class:`~xtr_security_core.TraceableVoter` when tracing is on.
        """
        voter_keys = tuple(builder.find_tagged_service_ids(VOTER_TAG))
        qualifiers = tuple(f"security_voter_{index}" for index in range(len(voter_keys)))
        for qualifier, key in zip(qualifiers, voter_keys, strict=True):
            builder.set_alias(
                VoterInterface,
                key[0],
                alias_qualifier=qualifier,
                target_qualifier=key[1],
            )
        _ = builder.get_definition(AccessDecisionManager).set_argument(
            "voter_qualifiers", qualifiers
        )

    @override
    async def boot(self) -> None:
        """Fill this kernel's scheme registry from every firewall's OpenAPI scheme.

        Read synchronously by the generated schema, so it is resolved once here:
        each firewall's entry-point scheme model, keyed by the firewall name. The
        firewall map is a scoped service, so it is resolved inside a unit of work.
        """
        from xtr_dependency_injection import unit_of_work  # noqa: PLC0415 -- boot-only

        container = self.container
        if container is None:  # pragma: no cover -- the kernel sets this before boot.
            message = "SecurityBundle.boot ran without a container"
            raise RuntimeError(message)
        if not self._firewall_names:
            return
        async with unit_of_work(container) as unit:
            firewall_map = await unit.get(FirewallMap)
            for name in self._firewall_names:
                if not firewall_map.has(name):
                    continue
                context = firewall_map.get(name)
                self._scheme_registry.register(name, context.scheme.model, scheme_name=name)


def _access_decision_manager_factory(
    strategy: AccessDecisionStrategyInterface,
    *,
    trace_votes: bool,
) -> Callable[..., Awaitable[AccessDecisionManager]]:
    """Return a factory building the decision manager from the collected voters.

    The voters are injected as a ``Mapping`` keyed by the qualifiers the bundle's
    ``process`` hook aliased them under, given as a definition argument the same
    hook fills; the dispatcher is injected only when tracing wraps each voter.
    """

    async def access_decision_manager(
        voters: Mapping[Hashable, VoterInterface],
        voter_qualifiers: tuple[str, ...],
        dispatcher: object | None = None,
    ) -> AccessDecisionManager:
        collected: list[VoterInterface] = [voters[qualifier] for qualifier in voter_qualifiers]
        if trace_votes:
            resolved = cast("EventDispatcherInterface", dispatcher)
            collected = [TraceableVoter(voter, resolved) for voter in collected]
        return AccessDecisionManager(collected, strategy)

    annotations: dict[str, object] = {
        "voters": Mapping[Hashable, VoterInterface],
        "return": AccessDecisionManager,
    }
    if trace_votes:
        annotations["dispatcher"] = EventDispatcherInterface
    access_decision_manager.__annotations__ = annotations
    return access_decision_manager


def _authorization_checker(
    token_storage: TokenStorageInterface,
    access_decision_manager: AccessDecisionManagerInterface,
) -> AuthorizationChecker:
    """Build the authorization checker over the request's storage and the manager."""
    return AuthorizationChecker(token_storage, access_decision_manager)


def _security_facade(
    token_storage: TokenStorageInterface,
    authorization_checker: AuthorizationCheckerInterface,
) -> Security:
    """Build the :class:`Security` facade over the request's storage and checker."""
    return Security(token_storage, authorization_checker)


def _scheme_middleware_factory(
    registry: FirewallSchemeRegistry,
) -> Callable[[], FirewallSchemeMiddlewareFactory]:
    """Return the middleware factory that activates ``registry`` per request."""

    def firewall_scheme_middleware() -> FirewallSchemeMiddlewareFactory:
        return FirewallSchemeMiddlewareFactory(registry)

    return firewall_scheme_middleware

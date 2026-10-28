"""The core security services: what every request's security runs on.

The role hierarchy, the trust resolver, the voters and the decision
manager they answer through, the request's token storage and the checker
and facade over it, the route markers' resolvers and the forgery checker,
the password hashers and the user providers — registered here, in the
order their dependencies answer in, so the bundle's own extension reads as
the orchestration it is: this, then the firewalls, then the console.
"""

from __future__ import annotations

from collections.abc import (
    Hashable,
    Mapping,
)
from typing import TYPE_CHECKING, cast

from xtr_clock import ClockInterface  # noqa: TC002 -- a factory signature the container reads
from xtr_dependency_injection.decorator.remove_if_missing import (
    REMOVE_IF_MISSING_TAG,
    markers_of,
)
from xtr_event_dispatcher_contracts import EventDispatcherInterface
from xtr_http_message_contracts.factory import (
    ResponseFactoryInterface,  # noqa: TC002 -- a factory signature the container reads
)
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
    TraceableAccessDecisionManager,
    TraceableVoter,
    UserAuthorizationCheckerInterface,
    VoterInterface,
)
from xtr_security_http import (
    CsrfTokenChecker,
    HttpUtils,
    IsGrantedChecker,
    SecurityTokenResolver,
    UserValueResolver,
)

from xtr_security.bundle._hasher_wiring import register_hashers
from xtr_security.bundle._voter_wiring import register_voters
from xtr_security.bundle._wiring import register_user_providers
from xtr_security.security import Security

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator

    from xtr_security.bundle.security_config import SecurityConfig

__all__ = ["register_core_security_services"]


def register_core_security_services(
    services: ServiceConfigurator,
    builder: ContainerBuilder,
    config: SecurityConfig,
    *,
    strategy: AccessDecisionStrategyInterface,
    trace_votes: bool,
) -> None:
    """Register the services every request's security runs on.

    The decision manager is registered over the strategy the configuration
    built and the voters the ``process`` hook collects, so the bundle's own
    extension hands both in and stays an orchestration. The trust resolver
    takes the application's clock while the clock bundle is active; the
    forgery checker carries its remove-if-missing markers, so it stays only
    while a firewall's wiring built the manager it answers through.
    """
    from xtr_dependency_injection import bundle_active  # noqa: PLC0415 -- read at registration time

    _ = services.instance(RoleHierarchy(config.role_hierarchy))
    services.alias(RoleHierarchyInterface, RoleHierarchy)
    if bundle_active(builder, "clock"):
        _ = services.set(_authentication_trust_resolver)
    else:
        _ = services.instance(AuthenticationTrustResolver())
    services.alias(AuthenticationTrustResolverInterface, AuthenticationTrustResolver)

    register_voters(services)
    _ = services.set(
        _access_decision_manager_factory(strategy, trace_votes=trace_votes)
    ).set_argument("voter_qualifiers", ())
    if trace_votes:
        _ = services.set(_traceable_access_decision_manager, lifetime="scoped").add_tag(
            "kernel.reset", method="reset"
        )
        services.alias(AccessDecisionManagerInterface, TraceableAccessDecisionManager)
        services.load("xtr_security.event_listener.vote_listener")
    else:
        services.alias(AccessDecisionManagerInterface, AccessDecisionManager)

    _ = services.set(TokenStorage, lifetime="scoped").add_tag("kernel.reset", method="reset")
    services.alias(TokenStorageInterface, TokenStorage)
    _ = services.set(_authorization_checker, lifetime="scoped")
    services.alias(AuthorizationCheckerInterface, AuthorizationChecker)
    services.alias(UserAuthorizationCheckerInterface, AuthorizationChecker)
    services.alias(GuestAuthorizationCheckerInterface, AuthorizationChecker)
    _ = services.set(_security_facade, lifetime="scoped")

    # The route markers' enforcement services, over the same request-scoped
    # storage and decision machinery. The CSRF checker carries its
    # remove-if-missing marker on the class; the tag the pass reads goes
    # on the definition, so the checker is dropped unless a token manager
    # is wired.
    _ = services.set(UserValueResolver, lifetime="scoped")
    _ = services.set(SecurityTokenResolver, lifetime="scoped")
    _ = services.set(IsGrantedChecker, lifetime="scoped")
    csrf_checker = services.set(CsrfTokenChecker, lifetime="scoped")
    for attributes in markers_of(CsrfTokenChecker):
        _ = csrf_checker.add_tag(REMOVE_IF_MISSING_TAG, **attributes)

    register_hashers(services, config)
    register_user_providers(services, config)

    # The redirect and URI helper the login flows answer through — one
    # per application, over the response factory every answer builds on.
    _ = services.set(_http_utils)


def _access_decision_manager_factory(
    strategy: AccessDecisionStrategyInterface,
    *,
    trace_votes: bool,
) -> Callable[..., Awaitable[AccessDecisionManager]]:
    """Return a factory building the decision manager from the collected voters."""

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


def _authentication_trust_resolver(clock: ClockInterface) -> AuthenticationTrustResolver:
    """Build the trust resolver reading recency from the application's clock."""
    return AuthenticationTrustResolver(clock=clock)


def _traceable_access_decision_manager(
    manager: AccessDecisionManager,
) -> TraceableAccessDecisionManager:
    """Build the request's traceable decision manager over the shared one."""
    return TraceableAccessDecisionManager(manager)


def _security_facade(
    token_storage: TokenStorageInterface,
    authorization_checker: AuthorizationCheckerInterface,
) -> Security:
    """Build the :class:`~xtr_security.Security` facade over the request's storage and checker."""
    return Security(token_storage, authorization_checker)


def _http_utils(responses: ResponseFactoryInterface) -> HttpUtils:
    """Build the redirect and URI helper the login flows answer through."""
    return HttpUtils(responses)

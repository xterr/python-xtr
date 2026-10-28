"""The voter wiring: the four built-ins, each tagged for the decision manager."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_security_core import (
    AuthenticatedVoter,
    AuthenticationTrustResolverInterface,
    ClosureVoter,
    RoleHierarchyInterface,
    RoleHierarchyVoter,
)
from xtr_security_http import OAuth2ScopeVoter

if TYPE_CHECKING:
    from xtr_dependency_injection import ServiceConfigurator

__all__ = ["VOTER_TAG", "register_voters"]

VOTER_TAG = "security.voter"
"""The tag every voter carries, so the decision manager collects them all."""


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

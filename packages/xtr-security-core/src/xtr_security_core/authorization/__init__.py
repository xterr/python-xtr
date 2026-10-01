"""Authorization: voters, strategies, the decision manager and the checkers over them."""

from __future__ import annotations

from .access_decision import AccessDecision
from .access_decision_manager import AccessDecisionManager
from .access_decision_manager_interface import AccessDecisionManagerInterface
from .authorization_checker import AuthorizationChecker
from .authorization_checker_interface import AuthorizationCheckerInterface
from .guest_authorization_checker_interface import GuestAuthorizationCheckerInterface
from .is_granted_context import IsGrantedContext
from .strategy import (
    AccessDecisionStrategyInterface,
    AffirmativeStrategy,
    ConsensusStrategy,
    PriorityStrategy,
    UnanimousStrategy,
)
from .voter import (
    Access,
    AuthenticatedVoter,
    CacheableVoterInterface,
    ClosureVoter,
    RoleHierarchyVoter,
    RoleVoter,
    TraceableVoter,
    Vote,
    Voter,
    VoterInterface,
)

__all__ = [
    "Access",
    "AccessDecision",
    "AccessDecisionManager",
    "AccessDecisionManagerInterface",
    "AccessDecisionStrategyInterface",
    "AffirmativeStrategy",
    "AuthenticatedVoter",
    "AuthorizationChecker",
    "AuthorizationCheckerInterface",
    "CacheableVoterInterface",
    "ClosureVoter",
    "ConsensusStrategy",
    "GuestAuthorizationCheckerInterface",
    "IsGrantedContext",
    "PriorityStrategy",
    "RoleHierarchyVoter",
    "RoleVoter",
    "TraceableVoter",
    "UnanimousStrategy",
    "Vote",
    "Voter",
    "VoterInterface",
]

"""The security core for xtr applications.

Users, tokens, roles, voters and the authorization decision — everything that
needs no HTTP edge and no JSON Web Tokens. This module gathers the public
surface so an application imports it from one place.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .authentication import (
    AuthenticationTrustResolver,
    AuthenticationTrustResolverInterface,
)
from .authentication.token import (
    AbstractToken,
    NullToken,
    OfflineToken,
    TokenInterface,
    UsernamePasswordToken,
)
from .authentication.token.storage import TokenStorage, TokenStorageInterface
from .authorization import (
    Access,
    AccessDecision,
    AccessDecisionManager,
    AccessDecisionManagerInterface,
    AccessDecisionStrategyInterface,
    AffirmativeStrategy,
    AuthenticatedVoter,
    AuthorizationChecker,
    AuthorizationCheckerInterface,
    CacheableVoterInterface,
    ClosureVoter,
    ConsensusStrategy,
    GuestAuthorizationCheckerInterface,
    IsGrantedContext,
    PriorityStrategy,
    RoleHierarchyVoter,
    RoleVoter,
    TraceableVoter,
    UnanimousStrategy,
    Vote,
    Voter,
    VoterInterface,
)
from .event import AuthenticationEvent, AuthenticationSuccessEvent, VoteEvent
from .exception import (
    AccessDeniedError,
    AccountExpiredError,
    AccountStatusError,
    AuthenticationCredentialsNotFoundError,
    AuthenticationError,
    AuthenticationServiceError,
    BadCredentialsError,
    CredentialsExpiredError,
    CustomUserMessageAccountStatusError,
    CustomUserMessageAuthenticationError,
    DisabledError,
    InsufficientAuthenticationError,
    InvalidArgumentError,
    LockedError,
    SecurityError,
    UnsupportedUserError,
    UserNotFoundError,
)
from .role import RoleHierarchy, RoleHierarchyInterface
from .user import (
    AttributesBasedUserProviderInterface,
    ChainUserChecker,
    ChainUserProvider,
    EnabledAwareInterface,
    EquatableInterface,
    InMemoryUser,
    InMemoryUserChecker,
    InMemoryUserProvider,
    OidcUser,
    PasswordUpgraderInterface,
    UserCheckerInterface,
    UserInterface,
    UserProviderInterface,
)

__all__ = [
    "AbstractToken",
    "Access",
    "AccessDecision",
    "AccessDecisionManager",
    "AccessDecisionManagerInterface",
    "AccessDecisionStrategyInterface",
    "AccessDeniedError",
    "AccountExpiredError",
    "AccountStatusError",
    "AffirmativeStrategy",
    "AttributesBasedUserProviderInterface",
    "AuthenticatedVoter",
    "AuthenticationCredentialsNotFoundError",
    "AuthenticationError",
    "AuthenticationEvent",
    "AuthenticationServiceError",
    "AuthenticationSuccessEvent",
    "AuthenticationTrustResolver",
    "AuthenticationTrustResolverInterface",
    "AuthorizationChecker",
    "AuthorizationCheckerInterface",
    "BadCredentialsError",
    "CacheableVoterInterface",
    "ChainUserChecker",
    "ChainUserProvider",
    "ClosureVoter",
    "ConsensusStrategy",
    "CredentialsExpiredError",
    "CustomUserMessageAccountStatusError",
    "CustomUserMessageAuthenticationError",
    "DisabledError",
    "EnabledAwareInterface",
    "EquatableInterface",
    "GuestAuthorizationCheckerInterface",
    "InMemoryUser",
    "InMemoryUserChecker",
    "InMemoryUserProvider",
    "InsufficientAuthenticationError",
    "InvalidArgumentError",
    "IsGrantedContext",
    "LockedError",
    "NullToken",
    "OfflineToken",
    "OidcUser",
    "PasswordUpgraderInterface",
    "PriorityStrategy",
    "RoleHierarchy",
    "RoleHierarchyInterface",
    "RoleHierarchyVoter",
    "RoleVoter",
    "SecurityError",
    "TokenInterface",
    "TokenStorage",
    "TokenStorageInterface",
    "TraceableVoter",
    "UnanimousStrategy",
    "UnsupportedUserError",
    "UserCheckerInterface",
    "UserInterface",
    "UserNotFoundError",
    "UserProviderInterface",
    "UsernamePasswordToken",
    "Vote",
    "VoteEvent",
    "Voter",
    "VoterInterface",
    "__version__",
]

try:
    __version__ = version("xtr-security-core")
except PackageNotFoundError:  # pragma: no cover
    # Running from a source tree with no installed metadata to read; having no
    # version is better than refusing to import.
    __version__ = "0+unknown"

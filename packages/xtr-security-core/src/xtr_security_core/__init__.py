"""The security core for xtr applications.

Users, tokens, roles, voters and the authorization decision — everything that
needs no HTTP edge and no JSON Web Tokens. This module gathers the public
surface so an application imports it from one place.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .authentication import (
    AuthenticationMethod,
    AuthenticationTrustResolver,
    AuthenticationTrustResolverInterface,
)
from .authentication.token import (
    AbstractToken,
    NullToken,
    OfflineTokenInterface,
    TokenInterface,
    UsernamePasswordToken,
)
from .authentication.token.storage import TokenStorage, TokenStorageInterface
from .authentication_events import AuthenticationEvents
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
    TraceableAccessDecisionManager,
    TraceableVoter,
    UnanimousStrategy,
    UserAuthorizationCheckerInterface,
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
    BadMethodCallError,
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
    MissingUserProvider,
    OAuth2User,
    OidcUser,
    OidcUserProvider,
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
    "AuthenticationEvents",
    "AuthenticationMethod",
    "AuthenticationServiceError",
    "AuthenticationSuccessEvent",
    "AuthenticationTrustResolver",
    "AuthenticationTrustResolverInterface",
    "AuthorizationChecker",
    "AuthorizationCheckerInterface",
    "BadCredentialsError",
    "BadMethodCallError",
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
    "MissingUserProvider",
    "NullToken",
    "OAuth2User",
    "OfflineTokenInterface",
    "OidcUser",
    "OidcUserProvider",
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
    "TraceableAccessDecisionManager",
    "TraceableVoter",
    "UnanimousStrategy",
    "UnsupportedUserError",
    "UserAuthorizationCheckerInterface",
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

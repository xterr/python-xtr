"""The HTTP edge of xtr security: firewalls, authenticators and access tokens.

The :class:`Firewall`, :class:`IsGranted` and :class:`CurrentUser` route
surface, the authenticator and passport machinery a firewall runs, the bearer
access-token extractors and the :class:`AccessTokenAuthenticator`, and the
listeners and events around a login. Built on the security core; needs FastAPI
and xtr-http-kernel.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .access_map import AccessMap
from .access_map_interface import AccessMapInterface
from .access_token import (
    AccessTokenExtractorInterface,
    AccessTokenHandlerInterface,
    ChainAccessTokenExtractor,
    FormEncodedBodyExtractor,
    HeaderAccessTokenExtractor,
    QueryAccessTokenExtractor,
)
from .authentication import (
    AuthenticationFailureHandlerInterface,
    AuthenticationSuccessHandlerInterface,
    AuthenticatorManager,
    AuthenticatorManagerInterface,
    ExposeSecurityLevel,
    is_sensitive,
    mask,
)
from .authenticator import (
    AbstractAuthenticator,
    AccessTokenAuthenticator,
    AuthenticatorInterface,
)
from .authenticator.passport import Passport, SelfValidatingPassport
from .authenticator.passport.badge import (
    BadgeInterface,
    PasswordUpgradeBadge,
    PreAuthenticatedUserBadge,
    UserBadge,
)
from .authenticator.passport.badge.user_badge import MAX_USERNAME_LENGTH
from .authenticator.passport.credentials import (
    CredentialsInterface,
    CustomCredentials,
    PasswordCredentials,
)
from .authenticator.token import PostAuthenticationToken
from .authorization import (
    AccessDeniedHandlerInterface,
    InsufficientScopeAccessDeniedHandler,
    OAuth2ScopeVoter,
    oauth2_scope,
    parse_oauth2_scope,
)
from .decorator.current_user import CurrentUser
from .decorator.is_granted import IsGranted
from .decorator.is_granted_context import IsGrantedContext
from .entry_point import AuthenticationEntryPointInterface
from .event import (
    AuthenticationTokenCreatedEvent,
    CheckPassportEvent,
    LoginFailureEvent,
    LoginSuccessEvent,
)
from .event_listener import (
    CheckCredentialsListener,
    PasswordMigratingListener,
    UserCheckerListener,
    UserProviderListener,
)
from .exception import (
    FirewallNotBootedError,
    InvalidAccessTokenError,
    UnknownFirewallError,
)
from .firewall import AccessListener, ExceptionListener, Firewall
from .firewall_context_interface import FirewallContextInterface
from .firewall_map import FirewallMap
from .firewall_map_interface import FirewallMapInterface
from .firewall_scheme import FirewallScheme
from .firewall_scheme_registry import (
    FirewallSchemeRegistry,
    active_firewall_schemes,
)
from .request_matcher import (
    CallableRequestMatcher,
    ChainRequestMatcher,
    HostRequestMatcher,
    IpRequestMatcher,
    MethodRequestMatcher,
    PathRequestMatcher,
    RequestMatcherInterface,
)

__all__ = [
    "MAX_USERNAME_LENGTH",
    "AbstractAuthenticator",
    "AccessDeniedHandlerInterface",
    "AccessListener",
    "AccessMap",
    "AccessMapInterface",
    "AccessTokenAuthenticator",
    "AccessTokenExtractorInterface",
    "AccessTokenHandlerInterface",
    "AuthenticationEntryPointInterface",
    "AuthenticationFailureHandlerInterface",
    "AuthenticationSuccessHandlerInterface",
    "AuthenticationTokenCreatedEvent",
    "AuthenticatorInterface",
    "AuthenticatorManager",
    "AuthenticatorManagerInterface",
    "BadgeInterface",
    "CallableRequestMatcher",
    "ChainAccessTokenExtractor",
    "ChainRequestMatcher",
    "CheckCredentialsListener",
    "CheckPassportEvent",
    "CredentialsInterface",
    "CurrentUser",
    "CustomCredentials",
    "ExceptionListener",
    "ExposeSecurityLevel",
    "Firewall",
    "FirewallContextInterface",
    "FirewallMap",
    "FirewallMapInterface",
    "FirewallNotBootedError",
    "FirewallScheme",
    "FirewallSchemeRegistry",
    "FormEncodedBodyExtractor",
    "HeaderAccessTokenExtractor",
    "HostRequestMatcher",
    "InsufficientScopeAccessDeniedHandler",
    "InvalidAccessTokenError",
    "IpRequestMatcher",
    "IsGranted",
    "IsGrantedContext",
    "LoginFailureEvent",
    "LoginSuccessEvent",
    "MethodRequestMatcher",
    "OAuth2ScopeVoter",
    "Passport",
    "PasswordCredentials",
    "PasswordMigratingListener",
    "PasswordUpgradeBadge",
    "PathRequestMatcher",
    "PostAuthenticationToken",
    "PreAuthenticatedUserBadge",
    "QueryAccessTokenExtractor",
    "RequestMatcherInterface",
    "SelfValidatingPassport",
    "UnknownFirewallError",
    "UserBadge",
    "UserCheckerListener",
    "UserProviderListener",
    "__version__",
    "active_firewall_schemes",
    "is_sensitive",
    "mask",
    "oauth2_scope",
    "parse_oauth2_scope",
]

try:
    __version__ = version("xtr-security-http")
except PackageNotFoundError:  # pragma: no cover
    # Running from a source tree with no installed metadata to read; having no
    # version is better than refusing to import.
    __version__ = "0+unknown"

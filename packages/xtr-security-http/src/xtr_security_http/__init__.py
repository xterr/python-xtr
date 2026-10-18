"""The HTTP edge of xtr security: firewalls, authenticators and access tokens.

The :class:`Firewall` — a subscriber over the kernel lifecycle's events — the
:class:`IsGranted` and :class:`CurrentUser` route surface, the authenticator
and passport machinery a firewall runs, the bearer access-token extractors and
the :class:`AccessTokenAuthenticator`, and the listeners and events around a
login. Built on the security core; needs FastAPI and xtr-http-kernel.
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
    UserAuthenticatorInterface,
    is_sensitive,
    mask,
)
from .authenticator import (
    AbstractAuthenticator,
    AccessTokenAuthenticator,
    AuthenticatorInterface,
    InteractiveAuthenticatorInterface,
    TraceableAuthenticator,
    TraceableAuthenticatorManagerListener,
    UnsupportedReasons,
)
from .authenticator.passport import Passport, SelfValidatingPassport
from .authenticator.passport.badge import (
    AuthenticationMethodBadge,
    BadgeInterface,
    CsrfTokenBadge,
    PasswordUpgradeBadge,
    PreAuthenticatedUserBadge,
    RememberMeBadge,
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
from .decorator.current_token import CurrentToken
from .decorator.current_user import CurrentUser
from .decorator.firewall_listener_order import FirewallListenerOrder, firewall_listener_order_of
from .decorator.is_csrf_token_valid import (
    SOURCE_HEADER,
    SOURCE_PAYLOAD,
    SOURCE_QUERY,
    IsCsrfTokenValid,
)
from .decorator.is_granted import IsGranted
from .decorator.is_granted_context import IsGrantedContext
from .entry_point import AuthenticationEntryPointInterface
from .event import (
    AuthenticationTokenCreatedEvent,
    CheckPassportEvent,
    InteractiveLoginEvent,
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
    InvalidAccessTokenError,
    MissingStateBagError,
    UnknownFirewallError,
)
from .firewall import (
    AbstractListener,
    AccessListener,
    AuthenticatorManagerListener,
    ExceptionListener,
    Firewall,
    FirewallListenerInterface,
)
from .firewall_context_interface import FirewallContextInterface
from .firewall_map import FirewallMap
from .firewall_map_interface import FirewallMapInterface
from .http_utils import HttpUtils
from .resolver import (
    CsrfTokenChecker,
    IsGrantedChecker,
    SecurityTokenResolver,
    UserValueResolver,
)
from .security_events import SecurityEvents
from .security_request_attributes import SecurityRequestAttributes

__all__ = [
    "MAX_USERNAME_LENGTH",
    "SOURCE_HEADER",
    "SOURCE_PAYLOAD",
    "SOURCE_QUERY",
    "AbstractAuthenticator",
    "AbstractListener",
    "AccessDeniedHandlerInterface",
    "AccessListener",
    "AccessMap",
    "AccessMapInterface",
    "AccessTokenAuthenticator",
    "AccessTokenExtractorInterface",
    "AccessTokenHandlerInterface",
    "AuthenticationEntryPointInterface",
    "AuthenticationFailureHandlerInterface",
    "AuthenticationMethodBadge",
    "AuthenticationSuccessHandlerInterface",
    "AuthenticationTokenCreatedEvent",
    "AuthenticatorInterface",
    "AuthenticatorManager",
    "AuthenticatorManagerInterface",
    "AuthenticatorManagerListener",
    "BadgeInterface",
    "ChainAccessTokenExtractor",
    "CheckCredentialsListener",
    "CheckPassportEvent",
    "CredentialsInterface",
    "CsrfTokenBadge",
    "CsrfTokenChecker",
    "CurrentToken",
    "CurrentUser",
    "CustomCredentials",
    "ExceptionListener",
    "ExposeSecurityLevel",
    "Firewall",
    "FirewallContextInterface",
    "FirewallListenerInterface",
    "FirewallListenerOrder",
    "FirewallMap",
    "FirewallMapInterface",
    "FormEncodedBodyExtractor",
    "HeaderAccessTokenExtractor",
    "HttpUtils",
    "InsufficientScopeAccessDeniedHandler",
    "InteractiveAuthenticatorInterface",
    "InteractiveLoginEvent",
    "InvalidAccessTokenError",
    "IsCsrfTokenValid",
    "IsGranted",
    "IsGrantedChecker",
    "IsGrantedContext",
    "LoginFailureEvent",
    "LoginSuccessEvent",
    "MissingStateBagError",
    "OAuth2ScopeVoter",
    "Passport",
    "PasswordCredentials",
    "PasswordMigratingListener",
    "PasswordUpgradeBadge",
    "PostAuthenticationToken",
    "PreAuthenticatedUserBadge",
    "QueryAccessTokenExtractor",
    "RememberMeBadge",
    "SecurityEvents",
    "SecurityRequestAttributes",
    "SecurityTokenResolver",
    "SelfValidatingPassport",
    "TraceableAuthenticator",
    "TraceableAuthenticatorManagerListener",
    "UnknownFirewallError",
    "UnsupportedReasons",
    "UserAuthenticatorInterface",
    "UserBadge",
    "UserCheckerListener",
    "UserProviderListener",
    "UserValueResolver",
    "__version__",
    "firewall_listener_order_of",
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

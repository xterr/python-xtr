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
    SenderConstraintInterface,
)
from .authentication import (
    AuthenticationFailureHandlerInterface,
    AuthenticationSuccessHandlerInterface,
    AuthenticationUtils,
    AuthenticatorManager,
    AuthenticatorManagerInterface,
    CustomAuthenticationFailureHandler,
    CustomAuthenticationSuccessHandler,
    DefaultAuthenticationFailureHandler,
    DefaultAuthenticationSuccessHandler,
    ExposeSecurityLevel,
    UserAuthenticatorInterface,
    is_sensitive,
    mask,
)
from .authenticator import (
    AbstractAuthenticator,
    AbstractLoginFormAuthenticator,
    AbstractPreAuthenticatedAuthenticator,
    AccessTokenAuthenticator,
    AuthenticatorInterface,
    FallbackUserLoader,
    FormLoginAuthenticator,
    HttpBasicAuthenticator,
    InteractiveAuthenticatorInterface,
    JsonLoginAuthenticator,
    LoginLinkAuthenticator,
    RememberMeAuthenticator,
    RemoteUserAuthenticator,
    TraceableAuthenticator,
    TraceableAuthenticatorManagerListener,
    UnsupportedReasons,
    X509Authenticator,
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
from .entry_point import (
    AuthenticationEntryPointInterface,
    FallbackAuthenticationEntryPointInterface,
    ReAuthenticationEntryPointInterface,
)
from .event import (
    AuthenticationTokenCreatedEvent,
    CheckPassportEvent,
    CheckRefreshedUserEvent,
    InteractiveLoginEvent,
    LoginFailureEvent,
    LoginSuccessEvent,
    LogoutEvent,
    SwitchUserEvent,
    TokenDeauthenticatedEvent,
)
from .event_listener import (
    AuthenticationProofsListener,
    CheckCredentialsListener,
    CheckRememberMeConditionsListener,
    ClearedCookie,
    ClearSiteDataListener,
    CookieClearingListener,
    CsrfProtectionListener,
    CsrfTokenClearingListener,
    DefaultLogoutListener,
    LoginThrottlingListener,
    PasswordMigratingListener,
    RememberMeListener,
    SessionLogoutListener,
    SessionStrategyListener,
    UserCheckerListener,
    UserProviderListener,
)
from .exception import (
    ExpiredLoginLinkError,
    ImpersonationError,
    InvalidAccessTokenError,
    InvalidCsrfTokenError,
    InvalidLoginLinkAuthenticationError,
    InvalidLoginLinkError,
    InvalidLoginLinkErrorInterface,
    InvalidSessionStrategyError,
    LogoutError,
    MissingSessionError,
    MissingStateBagError,
    UnknownFirewallError,
)
from .firewall import (
    AbstractListener,
    AccessListener,
    AuthenticatorManagerListener,
    ChannelListener,
    ContextListener,
    ExceptionListener,
    Firewall,
    FirewallListenerInterface,
    LogoutListener,
    RefreshUserResult,
    SwitchUserListener,
)
from .firewall_context_interface import FirewallContextInterface
from .firewall_map import FirewallMap
from .firewall_map_interface import FirewallMapInterface
from .http_utils import HttpUtils
from .impersonate import (
    ImpersonateUrlGenerator,
    ImpersonationForm,
    SwitchUserConfig,
    SwitchUserConfigLookupInterface,
)
from .login_link import (
    LoginLinkDetails,
    LoginLinkHandler,
    LoginLinkHandlerInterface,
)
from .logout import LogoutForm, LogoutUrlGenerator
from .rate_limiter import DefaultLoginRateLimiter
from .remember_me import (
    AbstractRememberMeHandler,
    PersistentRememberMeHandler,
    RememberMeCookie,
    RememberMeDetails,
    RememberMeHandlerInterface,
    ResponseListener,
    SignatureRememberMeHandler,
)
from .resolver import (
    CsrfTokenChecker,
    IsGrantedChecker,
    SecurityTokenResolver,
    UserValueResolver,
)
from .security_events import SecurityEvents
from .security_request_attributes import SecurityRequestAttributes
from .session import (
    SessionAuthenticationStrategy,
    SessionAuthenticationStrategyInterface,
)
from .util import get_target_path, remove_target_path, save_target_path

__all__ = [
    "MAX_USERNAME_LENGTH",
    "SOURCE_HEADER",
    "SOURCE_PAYLOAD",
    "SOURCE_QUERY",
    "AbstractAuthenticator",
    "AbstractListener",
    "AbstractLoginFormAuthenticator",
    "AbstractPreAuthenticatedAuthenticator",
    "AbstractRememberMeHandler",
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
    "AuthenticationProofsListener",
    "AuthenticationSuccessHandlerInterface",
    "AuthenticationTokenCreatedEvent",
    "AuthenticationUtils",
    "AuthenticatorInterface",
    "AuthenticatorManager",
    "AuthenticatorManagerInterface",
    "AuthenticatorManagerListener",
    "BadgeInterface",
    "ChainAccessTokenExtractor",
    "ChannelListener",
    "CheckCredentialsListener",
    "CheckPassportEvent",
    "CheckRefreshedUserEvent",
    "CheckRememberMeConditionsListener",
    "ClearSiteDataListener",
    "ClearedCookie",
    "ContextListener",
    "CookieClearingListener",
    "CredentialsInterface",
    "CsrfProtectionListener",
    "CsrfTokenBadge",
    "CsrfTokenChecker",
    "CsrfTokenClearingListener",
    "CurrentToken",
    "CurrentUser",
    "CustomAuthenticationFailureHandler",
    "CustomAuthenticationSuccessHandler",
    "CustomCredentials",
    "DefaultAuthenticationFailureHandler",
    "DefaultAuthenticationSuccessHandler",
    "DefaultLoginRateLimiter",
    "DefaultLogoutListener",
    "ExceptionListener",
    "ExpiredLoginLinkError",
    "ExposeSecurityLevel",
    "FallbackAuthenticationEntryPointInterface",
    "FallbackUserLoader",
    "Firewall",
    "FirewallContextInterface",
    "FirewallListenerInterface",
    "FirewallListenerOrder",
    "FirewallMap",
    "FirewallMapInterface",
    "FormEncodedBodyExtractor",
    "FormLoginAuthenticator",
    "HeaderAccessTokenExtractor",
    "HttpBasicAuthenticator",
    "HttpUtils",
    "ImpersonateUrlGenerator",
    "ImpersonationError",
    "ImpersonationForm",
    "InsufficientScopeAccessDeniedHandler",
    "InteractiveAuthenticatorInterface",
    "InteractiveLoginEvent",
    "InvalidAccessTokenError",
    "InvalidCsrfTokenError",
    "InvalidLoginLinkAuthenticationError",
    "InvalidLoginLinkError",
    "InvalidLoginLinkErrorInterface",
    "InvalidSessionStrategyError",
    "IsCsrfTokenValid",
    "IsGranted",
    "IsGrantedChecker",
    "IsGrantedContext",
    "JsonLoginAuthenticator",
    "LoginFailureEvent",
    "LoginLinkAuthenticator",
    "LoginLinkDetails",
    "LoginLinkHandler",
    "LoginLinkHandlerInterface",
    "LoginSuccessEvent",
    "LoginThrottlingListener",
    "LogoutError",
    "LogoutEvent",
    "LogoutForm",
    "LogoutListener",
    "LogoutUrlGenerator",
    "MissingSessionError",
    "MissingStateBagError",
    "OAuth2ScopeVoter",
    "Passport",
    "PasswordCredentials",
    "PasswordMigratingListener",
    "PasswordUpgradeBadge",
    "PersistentRememberMeHandler",
    "PostAuthenticationToken",
    "PreAuthenticatedUserBadge",
    "QueryAccessTokenExtractor",
    "ReAuthenticationEntryPointInterface",
    "RefreshUserResult",
    "RememberMeAuthenticator",
    "RememberMeBadge",
    "RememberMeCookie",
    "RememberMeDetails",
    "RememberMeHandlerInterface",
    "RememberMeListener",
    "RemoteUserAuthenticator",
    "ResponseListener",
    "SecurityEvents",
    "SecurityRequestAttributes",
    "SecurityTokenResolver",
    "SelfValidatingPassport",
    "SenderConstraintInterface",
    "SessionAuthenticationStrategy",
    "SessionAuthenticationStrategyInterface",
    "SessionLogoutListener",
    "SessionStrategyListener",
    "SignatureRememberMeHandler",
    "SwitchUserConfig",
    "SwitchUserConfigLookupInterface",
    "SwitchUserEvent",
    "SwitchUserListener",
    "TokenDeauthenticatedEvent",
    "TraceableAuthenticator",
    "TraceableAuthenticatorManagerListener",
    "UnknownFirewallError",
    "UnsupportedReasons",
    "UserAuthenticatorInterface",
    "UserBadge",
    "UserCheckerListener",
    "UserProviderListener",
    "UserValueResolver",
    "X509Authenticator",
    "__version__",
    "firewall_listener_order_of",
    "get_target_path",
    "is_sensitive",
    "mask",
    "oauth2_scope",
    "parse_oauth2_scope",
    "remove_target_path",
    "save_target_path",
]

try:
    __version__ = version("xtr-security-http")
except PackageNotFoundError:  # pragma: no cover
    # Running from a source tree with no installed metadata to read; having no
    # version is better than refusing to import.
    __version__ = "0+unknown"

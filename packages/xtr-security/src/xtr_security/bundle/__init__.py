"""The xtr-dependency-injection bundle for the xtr security family.

Re-exports the :class:`SecurityBundle`, every configuration class an application
writes, and the factory helpers a third-party bundle extends the family through,
so an application configures security from one import.
"""

from __future__ import annotations

from xtr_security_http import ExposeSecurityLevel

from xtr_security.access_token import (
    Oauth2TokenHandlerFactory,
    OidcTokenHandlerFactory,
    OidcUserInfoTokenHandlerFactory,
    ServiceTokenHandlerFactory,
    TokenHandlerFactoryInterface,
)
from xtr_security.access_token.add_token_handler_factory import add_token_handler_factory
from xtr_security.exception import InvalidConfigurationError
from xtr_security.factory import (
    AccessTokenFactory,
    AuthenticatorFactoryInterface,
    HttpBasicFactory,
    OidcLoginFactory,
)
from xtr_security.factory.add_authenticator_factory import add_authenticator_factory
from xtr_security.firewall_config import FirewallConfig
from xtr_security.user_provider import (
    ChainUserProviderFactory,
    InMemoryUserProviderFactory,
    ServiceUserProviderFactory,
    UserProviderFactoryInterface,
)
from xtr_security.user_provider.add_user_provider_factory import add_user_provider_factory

from .access_control_configs import AccessControlConfig
from .access_decision_manager_config import AccessDecisionManagerConfig
from .authenticator_configs import AccessTokenConfig, HttpBasicConfig
from .firewall_access_listener_name import firewall_access_listener_name
from .firewall_dispatcher_name import firewall_dispatcher_name
from .firewall_manager_listener_name import firewall_manager_listener_name
from .make_firewalls_event_dispatcher_traceable_pass import (
    MakeFirewallsEventDispatcherTraceablePass,
)
from .make_firewalls_manager_listener_traceable_pass import (
    MakeFirewallsManagerListenerTraceablePass,
)
from .oidc_configs import (
    OidcLoginConfig,
    OidcTokenGeneratorConfig,
    TokenEndpointAuthMethod,
)
from .password_hasher_configs import (
    AutoHasherConfig,
    HasherConfig,
    NativeHasherConfig,
    Pbkdf2HasherConfig,
    PlaintextHasherConfig,
    ServiceHasherConfig,
)
from .register_global_security_event_listeners_pass import RegisterGlobalSecurityEventListenersPass
from .security_bundle import SecurityBundle
from .security_config import SecurityConfig
from .sort_firewall_listeners_pass import SortFirewallListenersPass
from .token_handler_configs import (
    Oauth2TokenHandlerConfig,
    OidcTokenHandlerConfig,
    OidcUserInfoTokenHandlerConfig,
    ServiceTokenHandlerConfig,
    TokenHandlerConfig,
)
from .user_provider_configs import (
    ChainUserProviderConfig,
    InMemoryUserProviderConfig,
    ServiceUserProviderConfig,
    UserProviderConfig,
)

__all__ = [
    "AccessControlConfig",
    "AccessDecisionManagerConfig",
    "AccessTokenConfig",
    "AccessTokenFactory",
    "AuthenticatorFactoryInterface",
    "AutoHasherConfig",
    "ChainUserProviderConfig",
    "ChainUserProviderFactory",
    "ExposeSecurityLevel",
    "FirewallConfig",
    "HasherConfig",
    "HttpBasicConfig",
    "HttpBasicFactory",
    "InMemoryUserProviderConfig",
    "InMemoryUserProviderFactory",
    "InvalidConfigurationError",
    "MakeFirewallsEventDispatcherTraceablePass",
    "MakeFirewallsManagerListenerTraceablePass",
    "NativeHasherConfig",
    "Oauth2TokenHandlerConfig",
    "Oauth2TokenHandlerFactory",
    "OidcLoginConfig",
    "OidcLoginFactory",
    "OidcTokenGeneratorConfig",
    "OidcTokenHandlerConfig",
    "OidcTokenHandlerFactory",
    "OidcUserInfoTokenHandlerConfig",
    "OidcUserInfoTokenHandlerFactory",
    "Pbkdf2HasherConfig",
    "PlaintextHasherConfig",
    "RegisterGlobalSecurityEventListenersPass",
    "SecurityBundle",
    "SecurityConfig",
    "ServiceHasherConfig",
    "ServiceTokenHandlerConfig",
    "ServiceTokenHandlerFactory",
    "ServiceUserProviderConfig",
    "ServiceUserProviderFactory",
    "SortFirewallListenersPass",
    "TokenEndpointAuthMethod",
    "TokenHandlerConfig",
    "TokenHandlerFactoryInterface",
    "UserProviderConfig",
    "UserProviderFactoryInterface",
    "add_authenticator_factory",
    "add_token_handler_factory",
    "add_user_provider_factory",
    "firewall_access_listener_name",
    "firewall_dispatcher_name",
    "firewall_manager_listener_name",
]

"""The xtr-dependency-injection bundle for the xtr security family.

Re-exports the :class:`SecurityBundle`, every configuration class an application
writes, and the factory helpers a third-party bundle extends the family through,
so an application configures security from one import.
"""

from __future__ import annotations

from xtr_security_http import ExposeSecurityLevel

from xtr_security.access_token import (
    OidcTokenHandlerFactory,
    ServiceTokenHandlerFactory,
    TokenHandlerFactoryInterface,
)
from xtr_security.access_token.add_token_handler_factory import add_token_handler_factory
from xtr_security.exception import InvalidConfigurationError
from xtr_security.factory import AccessTokenFactory, AuthenticatorFactoryInterface
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
from .authenticator_configs import AccessTokenConfig
from .password_hasher_configs import (
    AutoHasherConfig,
    HasherConfig,
    NativeHasherConfig,
    Pbkdf2HasherConfig,
    PlaintextHasherConfig,
    ServiceHasherConfig,
)
from .security_bundle import SecurityBundle
from .security_config import SecurityConfig
from .token_handler_configs import (
    OidcTokenHandlerConfig,
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
    "InMemoryUserProviderConfig",
    "InMemoryUserProviderFactory",
    "InvalidConfigurationError",
    "NativeHasherConfig",
    "OidcTokenHandlerConfig",
    "OidcTokenHandlerFactory",
    "Pbkdf2HasherConfig",
    "PlaintextHasherConfig",
    "SecurityBundle",
    "SecurityConfig",
    "ServiceHasherConfig",
    "ServiceTokenHandlerConfig",
    "ServiceTokenHandlerFactory",
    "ServiceUserProviderConfig",
    "ServiceUserProviderFactory",
    "TokenHandlerConfig",
    "TokenHandlerFactoryInterface",
    "UserProviderConfig",
    "UserProviderFactoryInterface",
    "add_authenticator_factory",
    "add_token_handler_factory",
    "add_user_provider_factory",
]

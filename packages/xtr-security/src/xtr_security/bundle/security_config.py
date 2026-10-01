"""The one configuration an application writes to secure itself.

Gathers the firewalls, the user providers, the password hashers, the role
hierarchy, the access-control rules and the decision strategy into one frozen
value the bundle builds services from. Buildable with no arguments — the
zero-config path is no firewalls, the affirmative strategy, and the built-in
factories — so the bundle arrives, builds and boots even unconfigured.
"""

from __future__ import annotations

# The kernel reads a config's type hints at runtime, so every annotation on a
# field must be importable at runtime — none of these may hide under TYPE_CHECKING.
from collections.abc import Mapping, Sequence  # noqa: TC003 -- field type read at runtime
from dataclasses import dataclass, field
from importlib.util import find_spec

from xtr_security_http import ExposeSecurityLevel

from xtr_security.access_token import (
    OidcTokenHandlerFactory,
    ServiceTokenHandlerFactory,
    TokenHandlerFactoryInterface,
)
from xtr_security.bundle.access_control_configs import (
    AccessControlConfig,  # noqa: TC001 -- field type read at runtime
)
from xtr_security.bundle.access_decision_manager_config import AccessDecisionManagerConfig
from xtr_security.bundle.password_hasher_configs import (
    HasherConfig,  # noqa: TC001 -- field type read at runtime
)
from xtr_security.bundle.user_provider_configs import (
    UserProviderConfig,  # noqa: TC001 -- field type read at runtime
)
from xtr_security.exception import InvalidConfigurationError
from xtr_security.factory import AccessTokenFactory, AuthenticatorFactoryInterface
from xtr_security.firewall_config import (
    FirewallConfig,  # noqa: TC001 -- field type read at runtime
)
from xtr_security.user_provider import (
    ChainUserProviderFactory,
    InMemoryUserProviderFactory,
    ServiceUserProviderFactory,
    UserProviderFactoryInterface,
)

__all__ = ["SecurityConfig"]


def _no_firewalls() -> dict[str, FirewallConfig]:
    """The empty firewall mapping a zero-config application starts with."""
    return {}


def _no_providers() -> dict[str, UserProviderConfig]:
    """The empty user-provider mapping a zero-config application starts with."""
    return {}


def _no_hashers() -> dict[type | str, HasherConfig]:
    """The empty password-hasher mapping a zero-config application starts with."""
    return {}


def _no_role_hierarchy() -> dict[str, Sequence[str]]:
    """The empty role hierarchy a zero-config application starts with."""
    return {}


def _default_authenticator_factories() -> tuple[AuthenticatorFactoryInterface, ...]:
    """The authenticator factories every application starts with."""
    return (AccessTokenFactory(),)


def _oidc_extra_available() -> bool:
    """Tell whether xtr-security-http's ``oidc`` extra (joserfc, httpx) is installed."""
    return find_spec("joserfc") is not None and find_spec("httpx") is not None


def _default_token_handler_factories() -> tuple[TokenHandlerFactoryInterface, ...]:
    """The token-handler factories every application starts with.

    The OIDC handler joins only when its extra is installed, so an application
    without joserfc and httpx carries no factory that would import them.
    """
    factories: tuple[TokenHandlerFactoryInterface, ...] = (ServiceTokenHandlerFactory(),)
    if _oidc_extra_available():
        factories = (*factories, OidcTokenHandlerFactory())
    return factories


def _default_user_provider_factories() -> tuple[UserProviderFactoryInterface, ...]:
    """The user-provider factories every application starts with."""
    return (
        InMemoryUserProviderFactory(),
        ChainUserProviderFactory(),
        ServiceUserProviderFactory(),
    )


@dataclass(frozen=True, slots=True)
class SecurityConfig:
    """Everything the security bundle builds from, defaulted to a working nothing.

    Attributes:
        firewalls: The firewalls, in the order they are matched — first match
            wins — keyed by name.
        providers: The user providers, keyed by the name firewalls refer to.
        password_hashers: The hasher each user class, ``"module:Class"`` string
            or declared name is hashed by.
        role_hierarchy: The roles each role reaches, expanding a token's roles.
        access_control: The access-control rules, tried in order.
        access_decision_manager: How the voters' answers become one decision.
        expose_security_errors: How much of an authentication failure reaches the
            client.
        trace_votes: Whether every vote is announced as an event; ``None`` follows
            the kernel's debug flag.
        authenticator_factories: The factories that build firewalls'
            authenticators; the built-ins plus any a bundle prepended.
        token_handler_factories: The factories that build access-token handlers.
        user_provider_factories: The factories that build user providers.

    Raises:
        InvalidConfigurationError: When a firewall names a provider that is not
            declared, or an entry point that is not one of its authenticators.
    """

    firewalls: Mapping[str, FirewallConfig] = field(default_factory=_no_firewalls)
    providers: Mapping[str, UserProviderConfig] = field(default_factory=_no_providers)
    password_hashers: Mapping[type | str, HasherConfig] = field(default_factory=_no_hashers)
    role_hierarchy: Mapping[str, Sequence[str]] = field(default_factory=_no_role_hierarchy)
    access_control: tuple[AccessControlConfig, ...] = ()
    access_decision_manager: AccessDecisionManagerConfig = field(
        default_factory=AccessDecisionManagerConfig
    )
    expose_security_errors: ExposeSecurityLevel = ExposeSecurityLevel.NONE
    trace_votes: bool | None = None
    authenticator_factories: tuple[AuthenticatorFactoryInterface, ...] = field(
        default_factory=_default_authenticator_factories
    )
    token_handler_factories: tuple[TokenHandlerFactoryInterface, ...] = field(
        default_factory=_default_token_handler_factories
    )
    user_provider_factories: tuple[UserProviderFactoryInterface, ...] = field(
        default_factory=_default_user_provider_factories
    )

    def __post_init__(self) -> None:
        """Cross-check firewalls against providers and their own authenticators."""
        for name, firewall in self.firewalls.items():
            if firewall.provider is not None and firewall.provider not in self.providers:
                raise InvalidConfigurationError(
                    f'The firewall "{name}" names the provider "{firewall.provider}", '
                    f"which is not declared.",
                )

"""A firewall with two authenticators, an auth-needing rule, and no entry point.

A local bundle prepends a second authenticator factory building a distinct
authenticator type, so the firewall carries two authenticators; with an access
rule that needs authentication and no ``entry_point`` named, the build cannot
decide which authenticator answers an unauthenticated request, so it fails.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_dependency_injection import Bundle, as_bundle, configure, required_bundle
from xtr_security_core import InMemoryUser
from xtr_security_core.user.user_interface import UserInterface
from xtr_security_http import AbstractAuthenticator, SelfValidatingPassport, UserBadge

from xtr_security.bundle import (
    AccessControlConfig,
    AccessTokenConfig,
    AuthenticatorFactoryInterface,
    FirewallConfig,
    SecurityConfig,
    ServiceTokenHandlerConfig,
    add_authenticator_factory,
)
from xtr_security.bundle.security_bundle import SecurityBundle

if TYPE_CHECKING:
    from collections.abc import Sequence

    from starlette.requests import Request
    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator, ServiceKey
    from xtr_security_http.authenticator.passport.passport import Passport

__all__ = ["AmbiguousBundle", "SecondAuthenticator", "security"]


class _Handler:
    """A stand-in token handler class the access-token authenticator names."""


@dataclass(frozen=True, slots=True)
class SecondAuthenticatorConfig:
    """The configuration the second authenticator factory builds from."""


def _load(identifier: str) -> UserInterface:
    return InMemoryUser(identifier)


@final
class SecondAuthenticator(AbstractAuthenticator):
    """A second, distinct authenticator that never applies."""

    __slots__ = ()

    @override
    def supports(self, request: Request) -> bool | None:
        del request
        return False

    @override
    async def authenticate(self, request: Request) -> Passport:
        del request
        return SelfValidatingPassport(UserBadge("nobody", user_loader=_load))


@final
class SecondAuthenticatorFactory(AuthenticatorFactoryInterface):
    """Builds the second authenticator, so the firewall carries two of them."""

    __slots__ = ()

    @property
    @override
    def key(self) -> str:
        return "second"

    @property
    @override
    def priority(self) -> int:
        return 5

    @property
    @override
    def config_type(self) -> type:
        return SecondAuthenticatorConfig

    @override
    def create_authenticator(
        self,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
        firewall_name: str,
        config: object,
        user_provider: ServiceKey | None,
    ) -> Sequence[ServiceKey]:
        del builder, config, user_provider

        def second_authenticator() -> SecondAuthenticator:
            return SecondAuthenticator()

        second_authenticator.__name__ = f"second_authenticator_{firewall_name}"
        second_authenticator.__qualname__ = second_authenticator.__name__
        return (services.set(second_authenticator, qualifier=firewall_name, lifetime="scoped").key,)


@final
@required_bundle(SecurityBundle)
@as_bundle("ambiguous")
class AmbiguousBundle(Bundle):
    """Prepends the second authenticator factory so two authenticator kinds exist."""

    @override
    def prepend_extension(self, builder: ContainerBuilder) -> None:
        """Register the second authenticator factory through the seam."""
        builder.prepend_extension_config(
            "security", add_authenticator_factory(SecondAuthenticatorFactory())
        )


@configure
def security() -> SecurityConfig:
    """Return a firewall with two authenticators and an auth-needing rule."""
    return SecurityConfig(
        firewalls={
            "api": FirewallConfig(
                pattern=r"^/api",
                authenticators=(
                    AccessTokenConfig(token_handler=ServiceTokenHandlerConfig(_Handler)),
                    SecondAuthenticatorConfig(),
                ),
            )
        },
        access_control=(AccessControlConfig(path=r"^/api", attribute="IS_AUTHENTICATED"),),
    )

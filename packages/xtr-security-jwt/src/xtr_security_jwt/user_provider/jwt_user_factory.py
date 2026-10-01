"""The factory that builds a stateless user provider for a firewall."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

from xtr_security_jwt.bundle.jwt_user_provider_config import JwtUserProviderConfig
from xtr_security_jwt.security.user.jwt_user_provider import JwtUserProvider

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator, ServiceKey

    from xtr_security_jwt.security.user.jwt_user_interface import JwtUserInterface

__all__ = ["JwtUserFactory"]


@final
class JwtUserFactory:
    """Builds a :class:`~xtr_security_jwt.security.user.JwtUserProvider`.

    Registered onto the security bundle's user-provider registry under the key
    ``jwt``. A configured provider names a
    :class:`~xtr_security_jwt.bundle.JwtUserProviderConfig` with the class to
    build from a token's claims; this factory registers the provider under the
    provider's name so a firewall resolves it by that name.
    """

    __slots__ = ()

    @property
    def key(self) -> str:
        """Name this kind of provider ``jwt``."""
        return "jwt"

    @property
    def config_type(self) -> type:
        """Build instances of :class:`JwtUserProviderConfig`."""
        return JwtUserProviderConfig

    def create(
        self,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
        provider_name: str,
        config: object,
    ) -> ServiceKey:
        """Register the stateless provider under ``provider_name`` and return its key."""
        del builder
        settings = cast("JwtUserProviderConfig", config)
        provider = JwtUserProvider(cast("type[JwtUserInterface]", settings.user_class))
        return services.instance(provider, qualifier=provider_name).key

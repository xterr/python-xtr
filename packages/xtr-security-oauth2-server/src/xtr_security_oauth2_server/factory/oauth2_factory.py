"""The factory that builds a firewall's access-token authenticator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, final

# These annotate factory parameters and returns the container reads at runtime,
# so the marker, the qualifier helper and the types stay importable here.
from xtr_dependency_injection import Target, named_factory
from xtr_http_kernel.bridge import HttpMessageFactoryInterface
from xtr_security_core.user.user_provider_interface import UserProviderInterface

from xtr_security_oauth2_server.bundle.oauth2_authenticator_config import (
    OAuth2AuthenticatorConfig,
)
from xtr_security_oauth2_server.bundle.oauth2_server_config import OAuth2ServerConfig
from xtr_security_oauth2_server.resource_server import ResourceServer
from xtr_security_oauth2_server.security.authenticator.oauth2_authenticator import (
    OAuth2Authenticator,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator, ServiceKey

__all__ = ["OAuth2Factory"]

#: Where this authenticator sits in a firewall's order, mirroring the number the
#: reference bundle gives it: late, so an authenticator a deployment added of
#: its own gets the request first.
_OAUTH2_PRIORITY = -10


@final
class OAuth2Factory:
    """Builds an :class:`OAuth2Authenticator` for a firewall that accepts access tokens.

    Registered onto the security bundle's authenticator registry under the key
    ``oauth2``. A firewall names an
    :class:`~xtr_security_oauth2_server.bundle.OAuth2AuthenticatorConfig` and
    this builds the authenticator for it — over the shared resource server, and
    over that firewall's *own* user provider.

    One authenticator per firewall, and that is the whole reason this factory
    exists rather than a single registered service: the resource owner a token
    names is loaded from the provider of the firewall that read it, so an API
    serving staff from one store and customers from another resolves the same
    token to the right person on each.
    """

    __slots__ = ()

    @property
    def key(self) -> str:
        """Name this kind of authenticator ``oauth2``."""
        return "oauth2"

    @property
    def priority(self) -> int:
        """Run late, so a deployment's own authenticator sees the request first."""
        return _OAUTH2_PRIORITY

    @property
    def config_type(self) -> type:
        """Build instances of :class:`OAuth2AuthenticatorConfig`."""
        return OAuth2AuthenticatorConfig

    def create_authenticator(
        self,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
        firewall_name: str,
        config: object,
        user_provider: ServiceKey | None,
    ) -> Sequence[ServiceKey]:
        """Register the access-token authenticator for ``firewall_name``."""
        del builder, config
        authenticator = _authenticator_factory(firewall_name, user_provider)
        key = services.set(authenticator, qualifier=firewall_name, lifetime="scoped").key

        return (key,)


def _authenticator_factory(
    firewall_name: str,
    user_provider: ServiceKey | None,
) -> Callable[..., Awaitable[OAuth2Authenticator]]:
    """Return a factory building the authenticator from injected services.

    The bridge that turns the request into a message, the resource server that
    reads the token, the deployment's configuration and the firewall's own user
    provider are each injected by their type or key, so the factory is never
    handed the whole container.
    """

    async def oauth2_authenticator(
        messages: HttpMessageFactoryInterface,
        resource_server: ResourceServer,
        provider: UserProviderInterface,
        config: OAuth2ServerConfig,
    ) -> OAuth2Authenticator:
        return OAuth2Authenticator(
            messages,
            resource_server,
            provider,
            config.role_prefix,
        )

    oauth2_authenticator.__annotations__ = {
        "messages": HttpMessageFactoryInterface,
        "resource_server": ResourceServer,
        "provider": _qualified(user_provider)
        if user_provider is not None
        else UserProviderInterface,
        "config": OAuth2ServerConfig,
        "return": OAuth2Authenticator,
    }

    return named_factory(oauth2_authenticator, f"oauth2_authenticator_{firewall_name}")


def _qualified(key: ServiceKey) -> object:
    """Return the injection annotation selecting the service ``key`` names."""
    return Annotated[key[0], Target(key[1])]  # ty: ignore[invalid-type-form] -- runtime marker

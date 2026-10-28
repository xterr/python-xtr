"""The factory that builds a userinfo-endpoint token handler."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

from typing_extensions import override
from xtr_cache_contracts import (
    CacheInterface,  # noqa: TC002 -- a factory signature the container reads
)
from xtr_dependency_injection import named_factory
from xtr_http_client_contracts import (
    HttpClientInterface,
)
from xtr_security_http.access_token.access_token_handler_interface import (
    AccessTokenHandlerInterface,
)

from xtr_security.bundle.token_handler_configs import OidcUserInfoTokenHandlerConfig

from .token_handler_factory_interface import TokenHandlerFactoryInterface

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator, ServiceKey

__all__ = ["OidcUserInfoTokenHandlerFactory"]


@final
class OidcUserInfoTokenHandlerFactory(TokenHandlerFactoryInterface):
    """Builds a handler that reads the userinfo endpoint with the token.

    The handler lives in xtr-security-http's ``oidc`` extra, so it is imported
    only when one is built; the factory itself, and the interface the handler
    is registered under, carry no JOSE dependency.
    """

    __slots__ = ()

    @property
    @override
    def key(self) -> str:
        """Name this kind of handler ``oidc_user_info``."""
        return "oidc_user_info"

    @property
    @override
    def config_type(self) -> type:
        """Build instances of :class:`OidcUserInfoTokenHandlerConfig`."""
        return OidcUserInfoTokenHandlerConfig

    @override
    def create(
        self,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
        service_id: str,
        config: object,
    ) -> ServiceKey:
        """Register the userinfo handler service and return its key."""
        del builder
        settings = cast("OidcUserInfoTokenHandlerConfig", config)
        factory = named_factory(
            _oidc_user_info_handler_factory(settings),
            f"oidc_user_info_token_handler_{service_id}",
        )
        return services.set(factory, qualifier=service_id).key


def _oidc_user_info_handler_factory(
    settings: OidcUserInfoTokenHandlerConfig,
) -> Callable[..., AccessTokenHandlerInterface]:
    """Return a factory building the userinfo handler from ``settings``."""

    def oidc_user_info_token_handler(
        client: HttpClientInterface,
        cache: CacheInterface | None = None,
    ) -> AccessTokenHandlerInterface:
        from xtr_security_http.access_token.oidc import (  # noqa: PLC0415 -- guarded behind the oidc extra
            OidcUserInfoTokenHandler,
        )

        handler = OidcUserInfoTokenHandler(
            client.with_options(base_uri=settings.userinfo_base_uri),
            claim=settings.claim,
        )
        if cache is not None:
            # The configuration validated the key when it named the cache.
            handler.enable_discovery(cache, cast("str", settings.discovery_cache_key))
        return handler

    annotations: dict[str, object] = {
        "client": HttpClientInterface,
        "return": AccessTokenHandlerInterface,
    }
    if settings.discovery_cache is not None:
        annotations["cache"] = settings.discovery_cache
    oidc_user_info_token_handler.__annotations__ = annotations
    return oidc_user_info_token_handler

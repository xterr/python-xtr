"""The factory that builds an OIDC token handler for third-party issuers."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, cast, final

from typing_extensions import override
from xtr_dependency_injection import named_factory

# The container keys the handler service by this factory's evaluated return type,
# so the interface stays importable at runtime — it pulls in no joserfc.
from xtr_security_http.access_token.access_token_handler_interface import (  # noqa: TC002
    AccessTokenHandlerInterface,
)

from xtr_security.bundle.token_handler_configs import OidcTokenHandlerConfig

from .token_handler_factory_interface import TokenHandlerFactoryInterface

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator, ServiceKey
    from xtr_security_http.access_token.oidc import OidcKeySetProviderInterface

__all__ = ["OidcTokenHandlerFactory"]


@final
class OidcTokenHandlerFactory(TokenHandlerFactoryInterface):
    """Builds an OIDC token handler that verifies a third-party issuer's tokens.

    The handler and its key-set provider live in xtr-security-http's ``oidc``
    extra (joserfc, httpx); this factory imports them only when it builds one, so
    the bundle carries no JOSE or HTTP-client dependency until an application
    configures an OIDC firewall. The bundle registers this factory by default
    only when that extra is importable. Time comes from the wall clock, the
    injectable now-function the handler takes.
    """

    __slots__ = ()

    @property
    @override
    def key(self) -> str:
        """Name this kind of handler ``oidc``."""
        return "oidc"

    @property
    @override
    def config_type(self) -> type:
        """Build instances of :class:`OidcTokenHandlerConfig`."""
        return OidcTokenHandlerConfig

    @override
    def create(
        self,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
        service_id: str,
        config: object,
    ) -> ServiceKey:
        """Register the OIDC handler service and return its key."""
        del builder
        settings = cast("OidcTokenHandlerConfig", config)
        factory = named_factory(_oidc_handler_factory(settings), f"oidc_token_handler_{service_id}")
        return services.set(factory, qualifier=service_id).key


def _oidc_handler_factory(
    settings: OidcTokenHandlerConfig,
) -> Callable[[], AccessTokenHandlerInterface]:
    """Return a factory building the OIDC handler from ``settings``."""

    def oidc_token_handler() -> AccessTokenHandlerInterface:
        from xtr_security_http.access_token.oidc import (  # noqa: PLC0415 -- guarded behind the oidc extra
            OidcTokenHandler,
        )

        return OidcTokenHandler(
            _build_provider(settings),
            issuers=tuple(settings.issuers),
            audience=settings.audience,
            algorithms=tuple(settings.algorithms),
            claim=settings.claim,
            leeway=settings.leeway,
            enforce_at_jwt_type=settings.enforce_at_jwt_type,
            clock=lambda: int(time.time()),
        )

    return oidc_token_handler


def _build_provider(settings: OidcTokenHandlerConfig) -> OidcKeySetProviderInterface:
    """Build the key-set provider the configuration's single source describes."""
    import httpx  # noqa: PLC0415 -- guarded behind the oidc extra
    from xtr_security_http.access_token.oidc import (  # noqa: PLC0415 -- guarded behind the oidc extra
        DiscoveryOidcKeySetProvider,
        StaticOidcKeySetProvider,
    )

    if settings.keyset is not None:
        return StaticOidcKeySetProvider(settings.keyset)

    def client_factory() -> httpx.AsyncClient:
        return httpx.AsyncClient()

    return DiscoveryOidcKeySetProvider(
        base_uri=settings.discovery_uri,
        jwks_uri=settings.jwks_uri,
        http_client_factory=client_factory,
        allow_insecure_http=settings.allow_insecure_http,
    )

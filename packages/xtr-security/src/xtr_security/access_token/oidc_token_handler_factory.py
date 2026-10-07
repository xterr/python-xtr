"""The factory that builds an OIDC token handler for third-party issuers."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Protocol, cast, final, runtime_checkable

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

_DISCOVERY_TIMEOUT = 10.0
"""Seconds a discovery or JWKS fetch may take before it is abandoned.

Deliberately not the HTTP client library's own default. Discovery runs once
per issuer, off the request path, against a provider that may cold-start or
rotate keys, so a budget twice the general-purpose one costs nothing and
avoids a spurious failure on first use. Differing from the default is also
what makes the choice visible: a client that carries this timeout has been
configured, not left bare.
"""

_DISCOVERY_MAX_CONNECTIONS = 10
"""The ceiling on connections one provider's HTTP client keeps open."""


@runtime_checkable
class _AsyncCloseable(Protocol):
    """A key-set provider that holds a client to close when the kernel shuts down."""

    async def aclose(self) -> None:
        """Release the HTTP client the provider built, if any."""
        ...


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

    __slots__ = ("_closeables",)

    def __init__(self, closeables: list[_AsyncCloseable] | None = None) -> None:
        """Record where to collect providers to close on shutdown, if anywhere."""
        self._closeables = closeables

    def with_closeables(self, closeables: list[_AsyncCloseable]) -> OidcTokenHandlerFactory:
        """Return a copy that records the providers it builds into ``closeables``.

        The bundle owns the list and closes every collected provider on
        shutdown, so the HTTP client a discovery provider lazily builds does not
        outlive the kernel.
        """
        return OidcTokenHandlerFactory(closeables)

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
        factory = named_factory(
            _oidc_handler_factory(settings, self._closeables),
            f"oidc_token_handler_{service_id}",
        )
        return services.set(factory, qualifier=service_id).key


def _oidc_handler_factory(
    settings: OidcTokenHandlerConfig,
    closeables: list[_AsyncCloseable] | None,
) -> Callable[[], AccessTokenHandlerInterface]:
    """Return a factory building the OIDC handler from ``settings``."""

    def oidc_token_handler() -> AccessTokenHandlerInterface:
        from xtr_security_http.access_token.oidc import (  # noqa: PLC0415 -- guarded behind the oidc extra
            OidcTokenHandler,
        )

        return OidcTokenHandler(
            _build_provider(settings, closeables),
            issuers=tuple(settings.issuers),
            audience=settings.audience,
            algorithms=tuple(settings.algorithms),
            claim=settings.claim,
            leeway=settings.leeway,
            enforce_at_jwt_type=settings.enforce_at_jwt_type,
            clock=lambda: int(time.time()),
        )

    return oidc_token_handler


def _build_provider(
    settings: OidcTokenHandlerConfig,
    closeables: list[_AsyncCloseable] | None,
) -> OidcKeySetProviderInterface:
    """Build the key-set provider the configuration's single source describes."""
    import httpx  # noqa: PLC0415 -- guarded behind the oidc extra
    from xtr_security_http.access_token.oidc import (  # noqa: PLC0415 -- guarded behind the oidc extra
        DiscoveryOidcKeySetProvider,
        StaticOidcKeySetProvider,
    )

    if settings.keyset is not None:
        return StaticOidcKeySetProvider(settings.keyset)

    def client_factory() -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=httpx.Timeout(_DISCOVERY_TIMEOUT),
            limits=httpx.Limits(max_connections=_DISCOVERY_MAX_CONNECTIONS),
        )

    provider = DiscoveryOidcKeySetProvider(
        base_uri=settings.discovery_uri,
        jwks_uri=settings.jwks_uri,
        http_client_factory=client_factory,
        allow_insecure_http=settings.allow_insecure_http,
    )
    if closeables is not None:
        closeables.append(provider)
    return provider

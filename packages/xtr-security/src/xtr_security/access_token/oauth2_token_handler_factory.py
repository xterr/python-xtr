"""The factory that builds an OAuth2 introspection token handler."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

from typing_extensions import override
from xtr_cache_contracts import (
    CacheInterface,  # noqa: TC002 -- a factory signature the container reads
)
from xtr_clock import ClockInterface  # noqa: TC002 -- a factory signature the container reads
from xtr_dependency_injection import named_factory
from xtr_http_client_contracts import (
    HttpClientInterface,
)
from xtr_security_http.access_token.access_token_handler_interface import (
    AccessTokenHandlerInterface,
)

from xtr_security.bundle.token_handler_configs import Oauth2TokenHandlerConfig

from .token_handler_factory_interface import TokenHandlerFactoryInterface

if TYPE_CHECKING:
    from collections.abc import Callable

    from joserfc._keys import KeySetSerialization
    from joserfc.jwk import KeySet
    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator, ServiceKey

__all__ = ["Oauth2TokenHandlerFactory"]


@final
class Oauth2TokenHandlerFactory(TokenHandlerFactoryInterface):
    """Builds a handler that introspects a token with its authorization server.

    The scoped client — the application's own, carrying the introspection
    endpoint's base URI and this resource server's credentials — is built here
    through :meth:`~xtr_http_client_contracts.HttpClientInterface.with_options`,
    unless the configuration names a client service that carries its own. The
    handler and its signed-response verification live in xtr-security-http's
    ``oidc`` extra (joserfc); the key set a pinned JWKS document describes is
    imported only when the handler is built, so the bundle carries no JOSE
    dependency until an application configures one.
    """

    __slots__ = ()

    @property
    @override
    def key(self) -> str:
        """Name this kind of handler ``oauth2``."""
        return "oauth2"

    @property
    @override
    def config_type(self) -> type:
        """Build instances of :class:`Oauth2TokenHandlerConfig`."""
        return Oauth2TokenHandlerConfig

    @override
    def create(
        self,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
        service_id: str,
        config: object,
    ) -> ServiceKey:
        """Register the introspection handler service and return its key."""
        del builder
        settings = cast("Oauth2TokenHandlerConfig", config)
        factory = named_factory(
            _oauth2_handler_factory(settings),
            f"oauth2_token_handler_{service_id}",
        )
        return services.set(factory, qualifier=service_id).key


def _oauth2_handler_factory(
    settings: Oauth2TokenHandlerConfig,
) -> Callable[..., AccessTokenHandlerInterface]:
    """Return a factory building the introspection handler from ``settings``."""

    def oauth2_token_handler(
        client: HttpClientInterface,
        cache: CacheInterface | None = None,
        discovery_cache: CacheInterface | None = None,
        clock: ClockInterface | None = None,
    ) -> AccessTokenHandlerInterface:
        from xtr_security_http.access_token.oauth2 import (  # noqa: PLC0415 -- guarded behind the oidc extra
            Oauth2TokenHandler,
        )

        scoped = (
            client
            if settings.client is not None
            else client.with_options(
                base_uri=settings.introspection_base_uri,
                auth_basic=settings.credentials,
            )
        )
        handler = Oauth2TokenHandler(
            scoped,
            audiences=tuple(settings.audiences),
            issuer=settings.issuer,
            claim=settings.claim,
            clock=clock,
            allowed_time_drift=settings.allowed_time_drift,
        )
        if cache is not None:
            handler.enable_cache(cache, settings.cache_key_prefix, settings.cache_ttl)
        if settings.signed_response_algorithms is not None:
            handler.enable_signed_response(
                tuple(settings.signed_response_algorithms),
                cast("KeySet | None", _keyset(settings.signed_response_keyset)),
                settings.signed_response_enforce,
            )
        if discovery_cache is not None:
            handler.enable_signed_response_discovery(
                discovery_cache,
                scoped,
                cast("str", settings.signed_response_discovery_cache_key),
            )
        return handler

    annotations: dict[str, object] = {
        "client": settings.client if settings.client is not None else HttpClientInterface,
        "return": AccessTokenHandlerInterface,
    }
    if settings.cache is not None:
        annotations["cache"] = settings.cache
    if settings.signed_response_discovery_cache is not None:
        annotations["discovery_cache"] = settings.signed_response_discovery_cache
    oauth2_token_handler.__annotations__ = annotations
    return oauth2_token_handler


def _keyset(document: str | None) -> object:
    """Import the JWKS ``document`` into the key set the verifier reads.

    ``None`` — no key set pinned — is passed through: the handler then reads
    the keys from the issuer's metadata when that discovery is enabled, and
    refuses a signed response without keys otherwise.
    """
    if document is None:
        return None
    import json  # noqa: PLC0415 -- the standard library's reader, beside the gated import

    from joserfc.jwk import (  # noqa: PLC0415 -- guarded behind the oidc extra
        KeySet as JoserfcKeySet,
    )

    return JoserfcKeySet.import_key_set(cast("KeySetSerialization", json.loads(document)))
